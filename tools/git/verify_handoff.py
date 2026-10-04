"""Read-only check for a clean, published handoff between development agents."""
import argparse
import json
from pathlib import Path
import subprocess


def git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def check(path, require_pushed=False):
    problems = []
    status = git(path, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        problems.append(f"{len(status.splitlines())} archivo(s) pendiente(s)")
    branch = git(path, "branch", "--show-current")
    if not branch:
        problems.append("HEAD separado de una rama")
    if require_pushed:
        try:
            upstream = git(path, "rev-parse", "--abbrev-ref", "@{upstream}")
            ahead, behind = map(int, git(path, "rev-list", "--left-right", "--count",
                                        "HEAD..." + upstream).split())
            if ahead or behind:
                problems.append(f"{ahead} commit(s) sin subir; {behind} por integrar de {upstream}")
        except RuntimeError:
            problems.append("rama sin upstream remoto")
    return {"path": str(path), "branch": branch, "problems": problems}


def worktrees(root):
    paths = [Path(line[9:]) for line in git(root, "worktree", "list", "--porcelain").splitlines()
             if line.startswith("worktree ")]
    # Independent repository kept in the parent workspace; check it separately.
    for path in list(paths):
        nested = path / "step_harvest_web"
        if (nested / ".git").exists():
            paths.append(nested)
    return list(dict.fromkeys(paths))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-pushed", action="store_true")
    parser.add_argument("--all-worktrees", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    results = [check(path, args.require_pushed) for path in
               (worktrees(root) if args.all_worktrees else [root])]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            state = "; ".join(result["problems"]) or "limpio y publicado" if args.require_pushed else "; ".join(result["problems"]) or "limpio"
            print(f"{result['branch'] or '(detached)'} | {result['path']} | {state}")
    return int(any(result["problems"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
