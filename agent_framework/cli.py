import argparse, json
from pathlib import Path
from .core import AgentPipeline, Database

def main():
    parser = argparse.ArgumentParser(description="第三组岗位技能 Agent 框架")
    parser.add_argument("--db", default="data/challenge_cup.db")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    imp = sub.add_parser("import-jobs"); imp.add_argument("--file", required=True)
    prof = sub.add_parser("build-profile"); prof.add_argument("--cluster", required=True)
    mat = sub.add_parser("match"); mat.add_argument("--cluster", required=True); mat.add_argument("--resume", required=True); mat.add_argument("--resume-id", default="resume-input")
    rev = sub.add_parser("review"); rev.add_argument("--job-id", required=True); rev.add_argument("--skill", required=True); rev.add_argument("--decision", choices=["confirm","reject","add"], required=True); rev.add_argument("--reviewer", default=""); rev.add_argument("--reason", default="")
    args = parser.parse_args(); db = Database(args.db); db.init(); agent = AgentPipeline(db)
    if args.command == "init": result = {"database": str(Path(args.db).resolve()), "status": "ready"}
    elif args.command == "import-jobs": result = agent.import_jobs(json.loads(Path(args.file).read_text(encoding="utf-8")), source="cli")
    elif args.command == "build-profile": result = agent.build_profile(args.cluster)
    elif args.command == "match": result = agent.match(args.cluster, args.resume, args.resume_id)
    else: agent.review(args.job_id, args.skill, args.decision, args.reviewer, args.reason); result = {"status": "recorded"}
    print(json.dumps(result, ensure_ascii=False, indent=2)); db.close()

if __name__ == "__main__": main()
