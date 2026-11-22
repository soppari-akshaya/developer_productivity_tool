import requests
import logging

logger = logging.getLogger(__name__)

class GitHubService:
    BASE_URL = "https://api.github.com"

    @staticmethod
    def _headers(access_token=None):
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DeveloperProductivityTool/1.0"
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    @classmethod
    def get_user_profile(cls, access_token):
        try:
            resp = requests.get(f"{cls.BASE_URL}/user", headers=cls._headers(access_token), timeout=8)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching GitHub profile: {e}")
        return None

    @classmethod
    def get_user_repositories(cls, access_token, limit=15):
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/user/repos?sort=updated&per_page={limit}",
                headers=cls._headers(access_token),
                timeout=8
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching GitHub repos: {e}")
        return []

    @classmethod
    def get_public_user_repos(cls, username, limit=15):
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/users/{username}/repos?sort=updated&per_page={limit}",
                headers=cls._headers(),
                timeout=8
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching public GitHub repos: {e}")
        return []

    @classmethod
    def get_repo_details(cls, owner, repo, access_token=None):
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/repos/{owner}/{repo}",
                headers=cls._headers(access_token),
                timeout=8
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching repo details for {owner}/{repo}: {e}")
        return None

    @classmethod
    def get_repo_commits(cls, owner, repo, access_token=None, limit=10):
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/repos/{owner}/{repo}/commits?per_page={limit}",
                headers=cls._headers(access_token),
                timeout=8
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching commits for {owner}/{repo}: {e}")
        return []

    @classmethod
    def get_repo_pull_requests(cls, owner, repo, access_token=None, limit=10):
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/repos/{owner}/{repo}/pulls?state=all&per_page={limit}",
                headers=cls._headers(access_token),
                timeout=8
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching PRs for {owner}/{repo}: {e}")
        return []
