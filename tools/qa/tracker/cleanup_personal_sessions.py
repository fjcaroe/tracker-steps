"""Delete only the ephemeral proofs and their exact Odoo session files; no ORM startup."""
import configparser,json,os,re,sys
from pathlib import Path
assert os.geteuid()==0
facts=json.loads(Path(sys.argv[1]).read_text())
configs={'desarrollo.stepsapp.cl':('/etc/dev_odoo18.conf','LAB_TAREAS'),'cerroelplomo.stepsapp.cl':('/etc/odoo18-cerroelplomo.conf','CERRO_EL_PLOMO')}
for name in sys.argv[2:]:
 proof=Path(name);assert proof.parent==Path('/tmp') and proof.name.startswith('personal-session-')
 data=json.loads(proof.read_text());sid=data['session_id'];assert re.fullmatch(r'[A-Za-z0-9_-]{84}',sid)
 filename,db=configs[data['host']];cfg=configparser.ConfigParser(interpolation=None);cfg.read(filename);assert cfg['options']['db_name']==db
 base=Path(cfg['options']['data_dir']).resolve()/'sessions';session=base/sid[:2]/sid;assert session.parent.parent==base
 value=json.loads(session.read_text());assert value['db']==db and value['uid']==facts['source_user_id'] and value['login']==facts['login']
 session.unlink();proof.unlink();print('PERSONAL_BROWSER_SESSION_REMOVED '+db)
