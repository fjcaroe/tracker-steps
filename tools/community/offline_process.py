"""Run private Odoo validation with loopback only and no external network."""


def offline_odoo(command):
    # Arguments stay arguments: the fixed shell fragment never interpolates
    # a database name, path or credential into executable text. Callers use
    # PostgreSQL's existing Unix socket; local HTTP/PDF tests share loopback.
    return ['unshare', '--net', '--', 'sh', '-ec',
            'ip link set dev lo up; exec "$@"', 'steps-private-odoo', *command]
