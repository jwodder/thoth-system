#!/usr/bin/python
# Ensure a file exists at a given path, without touching it if it does exist.
# Missing parent directories are not automatically created.
from pathlib import Path
import traceback
from ansible.module_utils.basic import AnsibleModule


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "path": {"required": True, "type": "path"},
        },
        add_file_common_args=True,
        supports_check_mode=True,
    )
    path = Path(module.params["path"])
    file_args = module.load_file_common_arguments(module.params)
    changed = False
    try:
        if not path.exists(follow_symlinks=False):
            changed = True
            if not module.check_mode:
                path.touch()
                changed = module.set_fs_attributes_if_different(file_args, changed)
        else:
            changed = module.set_fs_attributes_if_different(file_args, changed)
    except Exception:
        module.fail_json(msg=traceback.format_exc())
    module.exit_json(changed=changed)


if __name__ == "__main__":
    main()
