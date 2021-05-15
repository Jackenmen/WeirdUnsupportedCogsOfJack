import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Literal, Tuple

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import NoParseOptional as Optional
from redbot.core.config import Config, Group
from redbot.core.utils.chat_formatting import box, humanize_list

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

GET_LATEST_TAGGED_COMMIT_QUERY = """
query getLatestTag {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    refs(refPrefix: "refs/tags/", last: 1) {
      nodes {
        name
        target {
          ... on Commit {
            oid
            committedDate
          }
        }
      }
    }
  }
}
"""
GET_COMMIT_HISTORY_QUERY = """
query getCommitHistory($after: String, $since: GitTimestamp) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, since: $since, after: $after) {
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
    return LINKIFY_PR_REFS_RE.sub(rf"[\0]({RED_GH_URL}/issues/\1)", text)


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
    async def getunreleasedcommits(self, ctx: commands.Context, milestone: str) -> None:
        """
        Get commits that were not released yet
        and might need to be put in the given milestone.
        """
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")

        async with self.session.post(
            "https://api.github.com/graphql",
            json={"query": GET_LATEST_TAGGED_COMMIT_QUERY},
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            json = await resp.json()
            tag_target = json["data"]["repository"]["refs"]["nodes"][0]["target"]
            committedDate = tag_target["committedDate"]

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
                        "since": committedDate,
                        "after": after,
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                json = await resp.json()
                data = json["data"]
                history = data["repository"]["defaultBranchRef"]["target"]["history"]

                for node in history["nodes"]:
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
                            f"({RED_GH_URL}/commits/{node['oid']})"
                            f" - {node['messageHeadline']}"
                        )

                page_info = history["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        embed = discord.Embed(title=f"Unreleased commits without {milestone} milestone")
        if commits_without_pr:
            embed.add_field(
                name="Commits without associated PR",
                value="\n".join(commits_without_pr),
                inline=False,
            )
        if commits_with_no_milestone:
            embed.add_field(
                name="Commits with no milestone",
                value="\n".join(commits_with_no_milestone),
                inline=False,
            )
        if commits_with_different_milestone:
            parts = []
            for milestone_title, commits in commits_with_different_milestone.items():
                parts.append(f"**{milestone_title}**")
                parts.extend(commits)
            embed.add_field(
                name="Commits with different milestone",
                value="\n".join(parts),
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.command()
    async def getcontributors(
        self, ctx: commands.Context, milestone: str, show_not_merged: bool = False
    ) -> None:
        """
        Get contributors for the given milestone in Red's repo.

        By default, this only shows PRs that have already been merged.
        You can pass True to `<show_not_merged>` to show both merged and not merged PRs.
        """
        after = None
        has_next_page = True
        authors = set()
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
                    authors.add(pr_node["author"]["login"])
                    reviews = pr_node["latestOpinionatedReviews"]["nodes"]
                    authors.update(
                        review_node["author"]["login"] for review_node in reviews
                    )

                page_info = pull_requests["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        authors_with_names = [
            (await self.get_name(github_username), github_username)
            for github_username in authors
        ]
        sorted_authors = sorted(authors_with_names, key=lambda t: t[0].lower())

        embed = discord.Embed(
            title=f"Contributors to milestone {milestone_title}",
            description=", ".join(
                map("[{0[0]}](https://github.com/{0[1]})".format, sorted_authors)
            ),
        )
        embed.add_field(
            name="RST formatted list (with custom display names)",
            value=box(
                ", ".join(
                    get_rst_string(display_name, github_username)
                    for display_name, github_username in sorted_authors
                )
            ),
        )

        await ctx.send(embed=embed)

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
