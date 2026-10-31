"""Operator-only command: python -m app.scripts.assign_role EMAIL ROLE."""

import argparse
from app.bootstrap import init_databases
from app.services.identity.repository import IdentityRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument(
        "role",
        choices=[
            "ANALYST",
            "MANAGER",
            "PRODUCTION_ACCOUNTANT",
            "FINANCE_ACCOUNTANT",
            "ADMIN",
        ],
    )
    args = parser.parse_args()
    init_databases()
    repo = IdentityRepository()
    user = repo.get_user_by_email(args.email)
    if user is None:
        parser.error("User does not exist")
    repo.assign_role(user.user_id, args.role)
    print("Role assigned")


if __name__ == "__main__":
    main()
