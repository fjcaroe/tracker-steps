"""Check the sealed Steps credit-note provider and original database storage during installation."""
import hashlib
import tarfile

from preflight_original_history_storage import require as check


def hash_file(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


MODULE = "step_cl_credit_note_draft"
RELEASE = {"__init__.py", "__manifest__.py", "hooks.py", "reversal.py", "i18n/es.po"}
METADATA = {"ir_module_module","ir_module_module_dependency","ir_model","ir_model_fields",
            "ir_model_fields_selection","ir_model_data","ir_model_constraint","ir_cron_trigger","ir_ui_view"}


def provider(archive, checksum, root):
    check(hash_file(archive) == checksum and len(checksum) == 64, "wrong-credit-note-package")
    directory = root / "addons"
    directory.mkdir(exist_ok=True)
    with tarfile.open(archive, "r:") as contents:
        members = contents.getmembers()
        check(len(members) == len(RELEASE) and {m.name for m in members} == {MODULE + "/" + f for f in RELEASE},
              "credit-note-members-differ")
        for member in members:
            check(member.isfile() and member.mode == 0o644, "unexpected-credit-note-member")
            file = directory / member.name
            data = contents.extractfile(member).read()
            file.parent.mkdir(parents=True, exist_ok=True)
            if not file.exists():
                file.write_bytes(data)
                file.chmod(0o644)
            check(file.read_bytes() == data and file.resolve(strict=True) == file, "unsealed-credit-note-code")
    check({f.relative_to(directory/MODULE).as_posix() for f in (directory/MODULE).rglob("*") if f.is_file()} == RELEASE,
          "unrecognized-credit-note-code")
    return directory


def compare_after(before, after, objects_before, objects_after, *, module_load):
    check(objects_before == objects_after and all(before[k] == after[k] for k in before
          if k not in ("public_tables","sequence_values")), "credit-note-SQL-objects-changed")
    check(before["public_tables"].keys() == after["public_tables"].keys(), "credit-note-table-set-changed")
    delta = sorted(name for name, values in before["public_tables"].items() if values != after["public_tables"][name])
    check(set(delta) <= (METADATA if module_load else set()), "credit-note-historical-rows-changed-" + str(delta))
    return delta
