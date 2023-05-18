"""
Script that automates "Jack's very private board ;)" project board.

Script requires JSON payload from GitHub's `issue_comment`, `pull_request`,
`pull_request_review`, or `pull_request_review_comment` webhook event
to be passed in first argument.

See links below for more info:
https://developer.github.com/webhooks/event-payloads/#issue_comment
https://developer.github.com/webhooks/event-payloads/#pull_request
https://developer.github.com/webhooks/event-payloads/#pull_request_review
https://developer.github.com/webhooks/event-payloads/#pull_request_review_comment

Note:
This script does not handle webhook requests itself,
it's up to server administrator to choose how to pass data to this script.
I recommend using https://github.com/adnanh/webhook
"""

import json
import os
import sys
from typing import Any, Dict

import requests


GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

PROJECT_NUMBER = 9
CHANGES_REQUESTED_COLUMN_ID = "MDEzOlByb2plY3RDb2x1bW4xMDkwMzE2OA=="
UPDATED_SINCE_REVIEW_COLUMN_ID = "MDEzOlByb2plY3RDb2x1bW4xMDkxMjAxNw=="

GQL_GET_PROJECT_CARDS_FOR_PR = """
query getProjectCardsForPullRequest($pr_number: Int!) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    pullRequest(number: $pr_number) {
      projectCards(first: 100) {
        nodes {
          id
          project {
            number
          }
          column {
            id
          }
        }
      }
    }
  }
}
""".strip()

GQL_MOVE_PROJECT_CARD_TO_COLUMN = """
mutation moveProjectCardToColumn($card_id: ID!, $column_id: ID!) {
  moveProjectCard(input:{cardId:$card_id, columnId: $column_id}) {
    clientMutationId
  }
}
""".strip()


class GQLError(Exception):
    def __init__(self, resp: requests.Response) -> None:
        super().__init__(f"GraphQL request failed. {resp.status_code=} {resp.text=}")


def request(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"token {GITHUB_TOKEN}"},
        json={"query": query, "variables": variables},
    )
    # non-200 will probably only happen for server errors, but still worth checking
    if resp.status_code != 200:
        raise GQLError(resp)
    response_data = resp.json()
    if "errors" in response_data:
        raise GQLError(resp)
    return response_data["data"]


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "This script requires exactly two argument"
            " with event type and JSON payload."
        )
        return 1

    event_type = sys.argv[1]
    payload = json.loads(sys.argv[2])
    pr_number = (payload.get("pull_request") or payload.get("issue"))["number"]
    action = payload["action"]

    if payload["sender"]["login"].lower() == "jackenmen":
        print("Ignoring my own actions.")
        return 0

    if event_type == "issue_comment":
        if action != "created":
            print(f"Action type ({action}) skipped.")
            return 0
        issue_data = payload["issue"]
        if "pull_request" not in issue_data:
            print("Ignoring comment on a non-PR.")
            return 0
    elif event_type == "pull_request":
        if action not in ("synchronize", "review_requested"):
            print(f"Action type ({action}) skipped.")
            return 0
    elif event_type == "pull_request_review":
        if action == "edited":
            print(f"Action type ({action}) skipped.")
            return 0
    elif event_type == "pull_request_review_comment":
        if action != "created":
            print(f"Action type ({action}) skipped.")
            return 0
    else:
        print("Unsupported event type.")
        return 1

    data = request(
        GQL_GET_PROJECT_CARDS_FOR_PR,
        {"pr_number": pr_number},
    )
    project_cards = data["repository"]["pullRequest"]["projectCards"]["nodes"]
    for card_data in project_cards:
        if card_data["project"]["number"] == PROJECT_NUMBER:
            break
    else:
        print("Ignoring pull request that isn't in my project.")
        return 0

    if card_data["column"]["id"] != CHANGES_REQUESTED_COLUMN_ID:
        print("Ignoring pull request that isn't in 'Changes requested' column.")
        return 0

    card_id = card_data["id"]
    try:
        request(
            GQL_MOVE_PROJECT_CARD_TO_COLUMN,
            {"card_id": card_id, "column_id": UPDATED_SINCE_REVIEW_COLUMN_ID},
        )
    except GQLError as exc:
        print(str(exc))
        return 1
    print(
        f"Moved the project card with ID {card_id}"
        " to 'Updated since my review' column."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
