#!/usr/bin/env python3

import json


def main():
    print(
        json.dumps(
            {
                "continue": True,
                "systemMessage": (
                    "Echo reminder: if you completed a task series, check whether new experience should "
                    "echo back to project memory or RadioHeader topics. If architecture changed, update "
                    "the project overview. If significant work completed, write a log entry."
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
