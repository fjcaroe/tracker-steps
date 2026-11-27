"""Validate the final Steps expense and credit-note checkpoint against all four earlier custody packages."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import tarfile

from verify_converted_backup import check, hash_file, read_json
from verify_steps_payment_release import verify as verify_166
from verify_steps_support_backup import compressed, file_archive, strong

DATABASE = "COMMUNITY_STEPS_EXPENSE_20261127U50E"
PARENT = "183a72362efaa1fc6f9d44e946b9f7219efb0760a2b80caabb6cad611cf4c021"
MODULES = {
    "step_cl_credit_note_draft": ("18.0.1.0.1", "LGPL-3", "5e8270b4a8bd25a91bc2bfaf4dd1db40be9be44a8bb1122449a46eaa7a03e552"),
    "step_expense_documents": ("18.0.1.0.0","AGPL-3","28b5ba914b7d0a2047b8a7478889e56bc323bf7f68e1da95de9f547e7d3e7e4a"),
}
PIECES = {"source.dump","snapshot.json.gz","sql-objects.json.gz","filestore.json.gz","filestore-delta.tar",
          "providers.json","functional-evidence.tar",*(name+".tar" for name in MODULES)}
REQUIRED = {"credit-native.json","credit-install.json","credit-update.json","credit-compare.json","expense-view.json",
            "expense-admission.json","support-native.json","support-integrated.json","business.json"}


def archive_tree(path, module):
    result = {}
    with tarfile.open(path, "r:") as archive:
        for member in archive:
            parts = member.name.split("/")
            check(member.isfile() and parts[0] == module and all(part not in ("",".","..") for part in parts)
                  and len(parts)>1 and member.name not in result, "unexpected-168-package-member")
            result[member.name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        manifest=ast.literal_eval(archive.extractfile(module+"/__manifest__.py").read().decode())
    check([manifest["version"],manifest["license"]]==list(MODULES[module][:2]), "wrong-168-provider-manifest")
    return result


def functional(path, manifest):
    with tarfile.open(path) as archive:
        files={}
        for member in archive:
            check(member.isfile() and Path(member.name).name==member.name and member.name.endswith(".json")
                  and member.name not in files,"unexpected-168-functional-evidence")
            files[member.name]=archive.extractfile(member).read()
    check({n:hashlib.sha256(v).hexdigest() for n,v in files.items()}==manifest and REQUIRED<=files.keys(),
          "wrong-168-functional-evidence")
    def unpack(name):
        return json.loads(files[name+".json"])
    credit=unpack("credit-compare")
    check(credit["providers"]==168 and credit["database"]==DATABASE and credit["original_documents"]==20
          and credit["operator_comparisons"]==60 and credit["assigned_folios"]==0 and credit["original_identities"]==5
          and credit["unchanged_tables"]==1115 and credit["native_sha256"]==manifest["credit-native.json"]
          and all(unpack("credit-"+phase)["release"]==MODULES["step_cl_credit_note_draft"][2]
                  for phase in ("install","update","compare")), "incomplete-168-credit-note-acceptance")
    original=unpack("support-native")
    support=unpack("support-integrated")
    check(support["db"]==DATABASE and support["modules"]==168 and support["thread"]==original["thread"]
          and support["http"]["result"]==original["http"]["result"] and support["reference_sha256"]==manifest["support-native.json"]
          and support["verified_http"]["tickets"]==5 and support["verified_http"]["attachments"]==2
          and len(support["pagination"]["steps"])==6, "missing-168-helpdesk-and-pages")
    check(unpack("expense-admission")["package"]==MODULES["step_expense_documents"][2],
          "missing-168-restored-expense-documents")
    business=unpack("business")
    check(manifest["business.json"]=="6a8e063966aedbc789f36afaeb8e2a537095028b71101ba7933c61795772c9ea"
          and business["providers"]==168 and business["database"]==DATABASE
          and all(manifest.get(k)==v for k,v in business["receipts"].items())
          and business["credit_notes"]["operator_comparisons"]==60 and business["credit_notes"]["assigned_folios"]==0
          and business["library_permission_decisions"]==686 and business["historical_link_calls"]==162
          and business["expenses"]["expenses"]==business["expenses"]["posted_entries"]==3, "missing-168-business-acceptance")
    return business


def verify(base, h3, fiscal, payments, folder, checksum, destination=None):
    check(hash_file(folder/"checkpoint.json")==checksum,"incorrect-168-checkpoint")
    proof=read_json(folder/"checkpoint.json")
    check(proof["source"]==DATABASE and proof["parent"]==PARENT and set(proof["files"])==PIECES, "incorrect-168-identity")
    for name,(size,sha) in proof["files"].items():
        path=folder/name
        check(path.stat().st_size==size and hash_file(path)==sha, "incorrect-168-piece-"+name)
    verify_166(base,h3,fiscal,payments,PARENT,destination)
    modules={**read_json(payments/"providers.json"), **{k:list(v[:2]) for k,v in MODULES.items()}}
    check(len(modules)==168 and read_json(folder/"providers.json")==modules, "incorrect-168-provider-inventory")
    for module,(_,_,sha) in MODULES.items():
        path=folder/(module+".tar")
        check(hash_file(path)==sha and archive_tree(path,module), "untested-168-extension")
    check(proof["schema_sha256"]==read_json(payments/"checkpoint.json")["schema_sha256"]
          and compressed(folder,"sql-objects.json.gz")==compressed(payments,"sql-objects.json.gz"), "168-schema-drift")
    sql=compressed(folder,"snapshot.json.gz")
    check(proof["tables"]==len(sql["public_tables"]) and proof["sequences"]==len(sql["sequence_values"])
          and proof["rows"]==sum(v[0] for v in sql["public_tables"].values())
          and proof["sql_objects"]==len(compressed(folder,"sql-objects.json.gz")), "168-SQL-inventory-drift")
    earlier=compressed(payments,"filestore.json.gz")
    tree=compressed(folder,"filestore.json.gz")
    changed={k:v for k,v in tree.items() if earlier.get(k)!=v}
    gone=sorted(earlier.keys()-tree.keys())
    check(sorted(changed)==proof["changed_files"] and gone==proof["removed_files"] and strong(tree)==proof["tree_sha256"],
          "168-physical-index-drift")
    if destination is not None:
        for item in set(gone)|(changed.keys()&earlier.keys()):
            path=destination/item
            check(re.fullmatch(r"(?:checklist/)?[0-9a-f]{2}/[0-9a-f]{40}",item) and
                  path.resolve(strict=True).is_relative_to(destination.resolve()) and hash_file(path)==earlier[item][1],
                  "wrong-parent-file-to-replace")
            path.unlink()
    file_archive(folder/"filestore-delta.tar",changed,destination,changed)
    if destination is not None:
        rebuilt={p.relative_to(destination).as_posix():[p.stat().st_size,hash_file(p)] for p in destination.rglob("*") if p.is_file()}
        check(rebuilt==tree,"168-physical-restoration-drift")
    functional(folder/"functional-evidence.tar",proof["evidence"])
    return {"source":DATABASE,"providers":168,"rows":proof["rows"],"tables":proof["tables"],"sequences":proof["sequences"],
            "sql_objects":proof["sql_objects"],"files":len(tree),"changed_files":len(changed),"removed_files":len(gone),
            "source_sql_sha256":proof["files"]["source.dump"][1],"checkpoint_sha256":checksum,"evidence":len(proof["evidence"])}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("base","h3","fiscal","payments","folder"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--sha256",required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.base,args.h3,args.fiscal,args.payments,args.folder,args.sha256)))
