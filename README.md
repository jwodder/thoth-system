Control system requirements:

- minimum Ansible version: 13.7

Target system requirements:

- Debian 13 (Trixie) or higher
- Python 3.12 or higher must already be installed
- There must already exist a non-root user with sudo powers that the control
  system can SSH in as.  Use this user as the `ansible_user`.
    - It is acceptable for this user to also be the `admin_user`.

Required Variables
==================

`backup` role
-------------

    backup_dropbox_oauth_app_key
    backup_dropbox_oauth_app_secret
    backup_dropbox_oauth_app_refresh_token
    backup_recipient_pubkey

`logsdb` role
-------------

    dailyreport_recipient  # if dailyreport enabled
