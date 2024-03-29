import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Literal, Tuple

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import NoParseOptional as Optional
from redbot.core.config import Config, Group
from redbot.core.utils.chat_formatting import box, humanize_list, text_to_file

from ..abc import MixinMeta


log = logging.getLogger("red.weirdjack.redhelper.helpers.changelog")

RED_GH_URL = "https://github.com/Cog-Creators/Red-DiscordBot"
GITHUB_USERS = "GITHUB_USERS"
GET_MILESTONE_CONTRIBUTORS_QUERY = """
query getMilestoneContributors(
  $milestone: String!,
  $after: String,
  $states: [PullRequestState!],
) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    milestones(first: 1, query: $milestone) {
      nodes {
        title
        pullRequests(first: 100, after: $after, states: $states) {
          nodes {
            title
            number
            author {
              login
            }
            latestOpinionatedReviews(first: 100, writersOnly: true) {
              nodes {
                author {
                  login
                }
              }
            }
          }
          pageInfo {
            endCursor
            hasNextPage
          }
        }
      }
    }
  }
}
"""
GET_PULL_REQUEST_QUERY = """
query getPullRequest($number: Int!) {
    repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
        pullRequest(number: $number) {
            id
            labels(first: 100) {
                nodes {
                    id
                }
            }
        }
    }
}
"""
ADD_AND_REMOVE_LABELS_MUTATION = """
mutation addAndRemoveLabels($pr_id: ID!, $to_add: [ID!]!, $to_remove: [ID!]!) {
  addLabelsToLabelable(input:{labelableId: $pr_id, labelIds: $to_add}) {
    clientMutationId
  }
  removeLabelsFromLabelable(input:{labelableId: $pr_id, labelIds: $to_remove}) {
    clientMutationId
  }
}
"""
LABEL_NAMES_TO_IDS = {
    "pending": "MDU6TGFiZWwxNDY5NDkyNzMw",
    "skipped": "MDU6TGFiZWwxOTIxMDcyNzYw",
    "added": "MDU6TGFiZWwxOTIxMDcxNzgw",
}

# technically not *all* but enough for what we use it for
GET_ALL_TAG_COMMITS_QUERY = """
query getAllTagCommits {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    refs(
        refPrefix: "refs/tags/"
        orderBy: {direction: DESC, field: TAG_COMMIT_DATE}
        first: 100
    ) {
      nodes {
        name
        target {
          ... on Commit {
            oid
          }
        }
      }
    }
  }
}
"""
GET_COMMIT_HISTORY_QUERY = """
query getCommitHistory($refQualifiedName: String!, $after: String) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    ref(qualifiedName: $refQualifiedName) {
      target {
        ... on Commit {
          history(first: 100, after: $after) {
            nodes {
              oid
              abbreviatedOid
              messageHeadline
              associatedPullRequests(first: 1) {
                nodes {
                  milestone {
                    title
                  }
                }
              }
            }
            pageInfo {
              endCursor
              hasNextPage
            }
          }
        }
      }
    }
  }
}
"""


def get_rst_string(display_name: str, github_username: str) -> str:
    if display_name == github_username:
        return f":ghuser:`{github_username}`"
    return f":ghuser:`{display_name} <{github_username}>`"


CHANGELOG_EDITORS = (473541068378341376,)


def is_changelog_editor():
    async def predicate(ctx: commands.Context) -> bool:
        return await ctx.bot.is_owner(ctx.author) or ctx.author.id in CHANGELOG_EDITORS

    return commands.check(predicate)


if TYPE_CHECKING:
    ChangelogLabelName = Literal["pending", "skipped", "added"]
else:

    class ChangelogLabelName(commands.Converter):
        async def convert(
            self, ctx: commands.Context, argument: str
        ) -> Literal["pending", "skipped", "added"]:
            argument = argument.lower()
            if argument not in LABEL_NAMES_TO_IDS:
                raise commands.BadArgument(
                    "Invalid label name.\n"
                    "Valid label names are: `pending`, `skipped`, `added`."
                )
            return argument


LINKIFY_PR_REFS_RE = re.compile(r"#(\d+)")


def linkify_pr_refs(text: str) -> str:
    return LINKIFY_PR_REFS_RE.sub(rf"[\g<0>]({RED_GH_URL}/issues/\1)", text)


class ChangelogMixin(MixinMeta):
    def __init__(self, bot: Red) -> None:
        super().__init__(bot)
        self.__config = Config.get_conf(
            None,
            176070082584248320,
            cog_name="RedHelper_Changelog",
            force_registration=True,
        )
        # {github_username: {...}}
        self.__config.init_custom(GITHUB_USERS, 1)
        self.__config.register_custom(GITHUB_USERS, display_name=None)

    def gh_user_config(self, github_username: str) -> Group:
        return self.__config.custom(GITHUB_USERS, github_username.lower())

    async def get_name(self, github_username: str) -> str:
        group = self.gh_user_config(github_username)
        return await group.display_name() or github_username

    @commands.command()
    async def getunreleasedcommits(
        self, ctx: commands.Context, milestone: str, branch: str = "V3/develop"
    ) -> None:
        """
        Get commits that were not released yet
        and might need to be put in the given milestone.
        """
        async with ctx.typing():
            text = await self._get_unreleased_commits_impl(
                ctx, milestone=milestone, branch=branch
            )
        await ctx.send(file=text_to_file(text, filename="unreleased_commits.md"))

    async def _get_unreleased_commits_impl(
        self, ctx: commands.Context, *, milestone: str, branch: str
    ) -> str:
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")

        async with self.session.post(
            "https://api.github.com/graphql",
            json={"query": GET_ALL_TAG_COMMITS_QUERY},
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            json = await resp.json()
            tag_commits = {
                node["target"]["oid"]: node["name"]
                for node in json["data"]["repository"]["refs"]["nodes"]
            }

        after = None
        has_next_page = True
        commits_without_pr: List[str] = []
        commits_with_no_milestone: List[str] = []
        commits_with_different_milestone: Dict[str, List[str]] = defaultdict(list)
        while has_next_page:
            async with self.session.post(
                "https://api.github.com/graphql",
                json={
                    "query": GET_COMMIT_HISTORY_QUERY,
                    "variables": {
                        "after": after,
                        "refQualifiedName": f"refs/heads/{branch}",
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                json = await resp.json()
                data = json["data"]
                history = data["repository"]["ref"]["target"]["history"]

                for node in history["nodes"]:
                    maybe_tag_name = tag_commits.get(node["oid"])
                    if maybe_tag_name is not None:
                        has_next_page = False
                        break
                    commits: Optional[List[str]] = None
                    associated_pr = next(
                        iter(node["associatedPullRequests"]["nodes"]), None
                    )
                    if associated_pr is None:
                        commits = commits_without_pr
                    elif (milestone_data := associated_pr["milestone"]) is None:
                        commits = commits_with_no_milestone
                    elif milestone_data["title"] != milestone:
                        commits = commits_with_different_milestone[
                            milestone_data["title"]
                        ]
                    if commits is not None:
                        commits.append(
                            f"- [{node['abbreviatedOid']}]"
                            f"({RED_GH_URL}/commit/{node['oid']})"
                            f" - {linkify_pr_refs(node['messageHeadline'])}"
                        )
                else:
                    page_info = history["pageInfo"]
                    after = page_info["endCursor"]
                    has_next_page = page_info["hasNextPage"]

        parts = []
        parts.append(f"# Unreleased commits without {milestone} milestone")
        if commits_without_pr:
            parts.append("\n## Commits without associated PR\n")
            parts.append("\n".join(commits_without_pr))
        if commits_with_no_milestone:
            parts.append("\n## Commits with no milestone\n")
            parts.append("\n".join(commits_with_no_milestone))
        if commits_with_different_milestone:
            parts.append("\n## Commits with different milestone\n")
            for milestone_title, commits in commits_with_different_milestone.items():
                parts.append(f"\n### {milestone_title}\n")
                parts.extend(commits)
        return "\n".join(parts)

    @commands.command()
    async def getcontributors(
        self, ctx: commands.Context, milestone: str, show_not_merged: bool = False
    ) -> None:
        """
        Get contributors for the given milestone in Red's repo.

        By default, this only shows PRs that have already been merged.
        You can pass True to `<show_not_merged>` to show both merged and not merged PRs.
        """
        async with ctx.typing():
            milestone_title, authors, reviewers = await self._get_contributor_data(
                milestone, show_not_merged=show_not_merged
            )
            contributors_with_names = [
                (await self.get_name(github_username), github_username)
                for github_username in (authors.keys() | reviewers.keys())
            ]

        sorted_contributors = sorted(contributors_with_names, key=lambda t: t[0].lower())
        embed = discord.Embed(
            title=f"Contributors to milestone {milestone_title}",
            description=", ".join(
                map("[{0[0]}](https://github.com/{0[1]})".format, sorted_contributors)
            ),
        )
        embed.add_field(
            name="RST formatted list (with custom display names)",
            value=box(
                ", ".join(
                    get_rst_string(display_name, github_username)
                    for display_name, github_username in sorted_contributors
                )
            ),
        )
        embed.add_field(
            name="GitHub release formatted list",
            value=box(
                ", ".join(
                    f"@{github_username}"
                    for display_name, github_username in sorted_contributors
                )
            ),
        )

        await ctx.send(embed=embed)

    @commands.command()
    async def getdetailedcontributors(
        self, ctx: commands.Context, milestone: str, show_not_merged: bool = False
    ) -> None:
        """
        Get contributors for the given milestone in Red's repo.

        By default, this only shows PRs that have already been merged.
        You can pass True to `<show_not_merged>` to show both merged and not merged PRs.
        """
        async with ctx.typing():
            milestone_title, authors, reviewers = await self._get_contributor_data(
                milestone, show_not_merged=show_not_merged
            )
            contributor_names = {
                github_username: await self.get_name(github_username)
                for github_username in (authors.keys() | reviewers.keys())
            }
        total_pr_number = sum(len(pulls) for pulls in authors.values())
        total_review_number = sum(len(pulls) for pulls in reviewers.values())

        parts = []
        parts.append(f"# Contributor statistics for milestone {milestone}")
        parts.append(f"\n## Number of PRs authored ({total_pr_number})\n")
        for author_name, pulls in sorted(authors.items(), key=lambda t: len(t[1]), reverse=True):
            parts.append(
                f"- [{contributor_names[author_name]}]"
                f"(https://github.com/{author_name}) - {len(pulls)}"
            )
        parts.append(f"\n## Number of reviews amongst all PRs ({total_review_number})\n")
        for author_name, pulls in sorted(reviewers.items(), key=lambda t: len(t[1]), reverse=True):
            parts.append(
                f"- [{contributor_names[author_name]}]"
                f"(https://github.com/{author_name}) - {len(pulls)}"
            )

        parts.append(f"\n## List of PRs by author ({total_review_number})\n")
        for author_name, pulls in sorted(authors.items(), key=lambda t: len(t[1]), reverse=True):
            parts.append(
                f"- [{contributor_names[author_name]}]"
                f"(https://github.com/{author_name}) - {len(pulls)}"
            )
            for number, title in pulls:
                parts.append(f"    - [{title} #{number}]({RED_GH_URL}/pull/{number})")

        parts.append(f"\n## List of reviews by reviewer ({total_review_number})\n")
        for author_name, pulls in sorted(reviewers.items(), key=lambda t: len(t[1]), reverse=True):
            parts.append(
                f"- [{contributor_names[author_name]}]"
                f"(https://github.com/{author_name}) - {len(pulls)}"
            )
            for number, title in pulls:
                parts.append(f"    - [{title} #{number}]({RED_GH_URL}/pull/{number})")

        await ctx.send(file=text_to_file("\n".join(parts), filename="contributor_details.md"))

    async def _get_contributor_data(
        self, milestone: str, *, show_not_merged: bool = False
    ) -> Tuple[str, Dict[str, List[Tuple[int, str]]], Dict[str, List[Tuple[int, str]]]]:
        after = None
        has_next_page = True
        authors = {}
        reviewers = {}
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")
        states = ["MERGED"]
        if show_not_merged:
            states.append("OPEN")
        while has_next_page:
            async with self.session.post(
                "https://api.github.com/graphql",
                json={
                    "query": GET_MILESTONE_CONTRIBUTORS_QUERY,
                    "variables": {
                        "milestone": milestone,
                        "after": after,
                        "states": states,
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                json = await resp.json()
                try:
                    milestone_data = json["data"]["repository"]["milestones"]["nodes"][0]
                except IndexError:
                    await ctx.send("Given milestone couldn't have been found.")
                milestone_title = milestone_data["title"]
                pull_requests = milestone_data["pullRequests"]
                nodes = pull_requests["nodes"]
                for pr_node in nodes:
                    pr_info = (pr_node["number"], pr_node["title"])
                    pr_author = pr_node["author"]["login"]
                    authors.setdefault(pr_author, []).append(pr_info)
                    reviews = pr_node["latestOpinionatedReviews"]["nodes"]
                    for review_node in reviews:
                        review_author = review_node["author"]["login"]
                        reviewers.setdefault(review_author, []).append(pr_info)

                page_info = pull_requests["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        return milestone_title, authors, reviewers

    @commands.is_owner()
    @commands.command()
    async def setcontributorname(
        self,
        ctx: commands.Context,
        github_username: str,
        display_name: Optional[str] = None,
    ):
        """
        Set custom display name for a contributor.

        Don't pass `display_name` to reset to GitHub username.
        """
        # I could do a comparison between `github_username` and `display_name`,
        # but one could only want to update the casing which would fail in that case
        group = self.gh_user_config(github_username)
        await group.display_name.set(display_name)
        if display_name is None:
            await ctx.send("Display name reset.")
        else:
            await ctx.send("Display name updated.")

    @is_changelog_editor()
    @commands.command(require_var_positional=True)
    async def changelog(
        self, ctx: commands.Context, label: ChangelogLabelName, *pr_numbers: int
    ) -> None:
        """
        Update the changelog label.

        Valid label names are: `pending`, `skipped`, `added`.
        """
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")
        add_label_id = LABEL_NAMES_TO_IDS.get(label)
        remove_label_ids = [
            label_id for label_id in LABEL_NAMES_TO_IDS.values() if label_id != add_label_id
        ]
        pr_ids: Dict[int, str] = {}
        # error lists
        not_found: List[int] = []
        already_labeled: List[int] = []
        unexpected_errors: List[int] = []

        for number in pr_numbers:
            async with self.session.post(
                "https://api.github.com/graphql",
                json={
                    "query": GET_PULL_REQUEST_QUERY,
                    "variables": {"number": number},
                },
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                json = await resp.json()
                pull_request = json["data"]["repository"]["pullRequest"]
                if pull_request is None:
                    not_found.append(number)
                    continue
                label_nodes = pull_request["labels"]["nodes"]
                if any(node["id"] == add_label_id for node in label_nodes):
                    already_labeled.append(number)
                    continue
                pr_ids[number] = pull_request["id"]

        success: List[int] = []

        for pr_number, pr_id in pr_ids.items():
            async with self.session.post(
                "https://api.github.com/graphql",
                json={
                    "query": ADD_AND_REMOVE_LABELS_MUTATION,
                    "variables": {
                        "pr_id": pr_id,
                        "to_add": [add_label_id],
                        "to_remove": remove_label_ids,
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                json = await resp.json()
                if "errors" in json:
                    unexpected_errors.append(pr_number)
                    log.error(
                        "Unexpected error occured when making labels mutation for PR #%s: %r",
                        pr_number,
                        json["errors"],
                    )
                else:
                    success.append(pr_number)

        errors = []
        if not_found:
            errors.append(
                f"PRs with these numbers couldn't be found: {humanize_list(not_found)}"
            )
        if already_labeled:
            prs_list = humanize_list(list(map("#{}".format, already_labeled)))
            errors.append(f"These PRs were already labeled properly: {prs_list}")
        if unexpected_errors:
            prs_list = humanize_list(list(map("#{}".format, unexpected_errors)))
            errors.append(
                f"Unexpected errors occured when updating labels for PRs: {prs_list}"
            )
        msg = []
        if success:
            prs_list = humanize_list(list(map("#{}".format, success)))
            msg.append(f"Labels have been updated successfully for PRs: {prs_list}")
        if errors:
            msg.append("\n".join(errors))
        await ctx.send("\n\n".join(msg))
