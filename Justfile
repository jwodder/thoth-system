run:
    ansible-playbook -i hosts --vault-password-file host_vars/thoth/secrets.pass playbook.yml

check:
    ansible-playbook --check --diff -i hosts --vault-password-file host_vars/thoth/secrets.pass playbook.yml

lint:
    ANSIBLE_LIBRARY=library ansible-lint
