from os import getenv
from os import environ
import argparse
from typing import Any
from dataclasses import dataclass, field
import tempfile
import pathlib
import subprocess
import re
import requests
import dateutil
from dotenv import load_dotenv


@dataclass
class PracticeGrading:
    """A python bindings to practice grading API"""

    url: str = "http://localhost:8080/api"
    login: str = "test"
    password: str = "test"
    cached_data: Any = field(default=None, init=False)

    def fetch_all(self) -> dict:
        if self.cached_data is not None:
            return self.cached_data

        creds = {"userName": self.login, "password": self.password}

        response = requests.post(self.url + "/login", json=creds, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Cannot authenticate: {response.status_code}")
        token = response.json()["token"]

        response = requests.get(self.url + "/meetings", headers={"Authorization": "Bearer " + token}, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Cannot fetch meetings data: {response.status_code}")
        self.cached_data = response.json()

        return self.cached_data

    def find_meeting(self, m_id: int) -> dict | None:
        data = self.fetch_all()

        for m in data:
            if m["id"] == m_id:
                return m
        return None

    def find_talk(self, t_id: int) -> dict | None:
        data = self.fetch_all()

        for m in data:
            for t in m["studentWorks"]:
                if t["id"] == t_id:
                    return t
        return None


@dataclass
class Analyzer:
    """Repo analyer"""

    model: str = "opencode/big-pickle"
    repo_limit: int = 30000

    @staticmethod
    def get_repo_size(repo: str) -> int:
        m = re.fullmatch(r"https?:\/\/github.com/([\w.-]+)\/([\w.-]+)(\.git)?.*", repo)
        if not m:
            raise RuntimeError(f"Cannot parse str '{repo}' as github repo")

        response = requests.get(f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}", timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Cannot get repo size: {response.status_code}")

        data = response.json()
        return data["size"]

    def analyze_folder(self, path: str) -> str:
        current_folder = pathlib.Path(__file__).resolve().parent
        prompt = "Analyze the project in the current folder"
        cmdline = (
            f"timeout 3600 "
            f"stdbuf -o0 "
            f"opencode --agent student-repo-reviewer --model '{self.model}' --dir '{path}' run '{prompt}' --format json "
            f"| tee -a /tmp/pr-opencode.log "
            f"| jq -r 'select(.type==\"text\") | .part.text'"
        )
        my_env = environ.copy()
        my_env["OPENCODE_CONFIG_DIR"] = str(current_folder / "opencode")

        # Must run via shell to mitigate strange opencode output behavior
        result = subprocess.run(cmdline, check=False, env=my_env, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            return f"opencode failed: {result.stdout} {result.stderr}"
        return result.stdout

    def analyze_repo(self, link: str) -> str:
        with tempfile.TemporaryDirectory() as workspace:
            my_env = environ.copy()
            my_env["GIT_TERMINAL_PROMPT"] = "0"
            match1 = re.fullmatch(r"(https?:\/\/github.com/[\w.-]+\/[\w.-]+(\.git)?)\/?(tree\/.*)?", link)
            match2 = re.fullmatch(r"(https?:\/\/github.com/[\w.-]+\/[\w.-]+(\.git)?)\/pull\/([\d]+)", link)
            repo = None
            if match1:
                repo = match1.group(1)
            if match2:
                repo = match2.group(1)
            if repo is None:
                raise RuntimeError("Unknown link format")

            # First, evaluate the size of the repo. Do not clone large repos
            size = self.get_repo_size(repo)
            if size > self.repo_limit:
                raise RuntimeError(f"Repo size too large: {size}Kb > {self.repo_limit}Kb")

            # Now, we can clone the repo
            subprocess.run(["git", "clone", repo, workspace], check=True, env=my_env)
            if match2:
                subprocess.run(
                    ["git", "-C", workspace, "fetch", "origin", f"pull/{match2.group(3)}/head:PR_ANALYZER"],
                    check=True,
                    env=my_env,
                )
                subprocess.run(["git", "-C", workspace, "checkout", "PR_ANALYZER"], check=True, env=my_env)

            return self.analyze_folder(workspace)

    def analyze_repos(self, lst: str) -> list[str]:
        if lst is None:
            raise RuntimeError("Repo not provided: empty")

        repos = lst.split()
        if len(repos) == 0:
            raise RuntimeError("Repo not provided: empty")

        if repos[0] == "NDA":
            raise RuntimeError("Repo not provided: NDA")

        result = []
        for link in repos:
            try:
                result.append(self.analyze_repo(link))
            except RuntimeError as e:
                result.append(str(e))

        return result


@dataclass
class CLI:
    """CLI handlers"""

    pg: Any
    analyzer: Any

    def handle_list(self, args) -> None:
        l = self.pg.fetch_all()
        if args.raw:
            print(l)
            return
        for m in l:
            print(f"{m['id']} at {dateutil.parser.parse(m['dateAndTime']).date()}")

    def handle_show_meeting(self, args) -> None:
        m = self.pg.find_meeting(args.id)
        if m is None:
            print(f"Cannot find meeting {args.id}")
            return

        if args.raw:
            print(m)
            return
        print(f"id: {m['id']}")
        print(f"location: {m['auditorium']}")
        print(f"time: {dateutil.parser.parse(m['dateAndTime']).date()}")
        print("students:")
        for s in m["studentWorks"]:
            print(f"\t{s['id']}: {s['studentName']}, {s['theme']}")

    def handle_show_talk(self, args) -> None:
        t = self.pg.find_talk(args.id)
        if t is None:
            print(f"Cannot find talk {args.id}")
            return

        if args.raw:
            print(t)
            return
        print(f"id: {t['id']}")
        print(f"student: {t['studentName']}")
        print(f"info: {t['info']}")
        print(f"topic: {t['theme']}")
        print(f"advisor: {t['supervisor']}")
        print(f"consultant: {t['consultant']}")
        print(f"reviewer: {t['reviewer']}")
        print(f"repos: {t['codeLink']}")
        print(f"final mark: {t['finalMark']}")

    def handle_analyze_meeting(self, args) -> None:
        m = self.pg.find_meeting(args.id)
        if m is None:
            print(f"Cannot find meeting {args.id}")
            return

        print(f"Processing meeting {m['id']}: {dateutil.parser.parse(m['dateAndTime']).date()}")

        folder_path = None
        if isinstance(args.output, str):
            folder_path = pathlib.Path(args.output) / f"{dateutil.parser.parse(m['dateAndTime']).date()} {m['id']}"
            folder_path.mkdir(parents=True, exist_ok=True)

        for t in m["studentWorks"]:
            print(f"Processing student {t['studentName']}")
            try:
                rv = self.analyzer.analyze_repos(t["codeLink"])
            except RuntimeError as e:
                rv = [str(e)]
            if folder_path is not None:
                student_path = folder_path / f"{t['id']} {t['studentName']}.md"
                student_path.write_text("\n".join(rv) + "\n", encoding="utf-8")
            else:
                print("\n".join(rv))

    def handle_analyze_talk(self, args) -> None:
        t = self.pg.find_talk(args.id)
        if t is None:
            print(f"Cannot find talk {args.id}")
            return

        print(f"Processing student {t['studentName']}")
        rv = []
        try:
            rv = self.analyzer.analyze_repos(t["codeLink"])
        except RuntimeError as e:
            rv = [str(e)]

        if isinstance(args.output, str):
            pathlib.Path(args.output).write_text("\n".join(rv) + "\n", encoding="utf-8")
        else:
            print("\n".join(rv))


def build_parser(cli: CLI) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI for practice grading service")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    list_parser = subparsers.add_parser("list", help="List all meetings")
    list_parser.add_argument("--raw", action="store_true")
    list_parser.set_defaults(func=cli.handle_list)

    show_meeting_parser = subparsers.add_parser("show-meeting", help="Show specific meeting")
    show_meeting_parser.add_argument("id", type=int, help="meeting ID")
    show_meeting_parser.add_argument("--raw", action="store_true")
    show_meeting_parser.set_defaults(func=cli.handle_show_meeting)

    show_talk_parser = subparsers.add_parser("show-talk", help="Show specific talk")
    show_talk_parser.add_argument("id", type=int, help="talk ID")
    show_talk_parser.add_argument("--raw", action="store_true")
    show_talk_parser.set_defaults(func=cli.handle_show_talk)

    analyze_parser = subparsers.add_parser("analyze-meeting", help="Analyze all talks in specified meeting")
    analyze_parser.add_argument("id", type=int, help="meeting ID")
    analyze_parser.add_argument("-o", "--output", type=str, default=None, help="Write result to folder")
    analyze_parser.set_defaults(func=cli.handle_analyze_meeting)

    analyze_parser = subparsers.add_parser("analyze-talk", help="Analyze specified talk repos")
    analyze_parser.add_argument("id", type=int, help="talk ID")
    analyze_parser.add_argument("-o", "--output", type=str, default=None, help="Write result to file")
    analyze_parser.set_defaults(func=cli.handle_analyze_talk)

    return parser


def main() -> None:
    load_dotenv()

    api_url = getenv("PRACTICE_GRADING_URL", "http://127.0.0.1:8080")
    login = getenv("PRACTICE_GRADING_LOGIN", "login")
    password = getenv("PRACTICE_GRADING_PASSWORD", "password")
    model = getenv("LLM_MODEL", "opencode/big-pickle")

    pg = PracticeGrading(url=api_url, login=login, password=password)
    analyzer = Analyzer(model=model)
    cli = CLI(pg=pg, analyzer=analyzer)

    parser = build_parser(cli)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
