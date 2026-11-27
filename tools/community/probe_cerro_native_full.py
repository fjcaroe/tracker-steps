import json,sys
sys.path.insert(0,'/opt/steps-validation/community-cerro-studio-strict-20261126U42C/tools')
from probe_cerro_farm_directory import capture
from probe_cerro_shared_farms import exercise
from probe_cerro_studio_fullread import capture as fullread
from probe_cerro_studio_navigation import capture as routes
assert env.ref('step_cerro_studio_farms.farms')==env.ref('step_cerro_studio_agriculture.farms')
rt=routes(env);assert all(rt['direct_menu_routes'].values())
x=fullread(env);assert sum('value_sha256' in item for item in x.values())==23
print('CERRO_DIRECTORY',json.dumps(dict(directory=capture(env),rights=exercise(env),fullread=x,routes=rt),sort_keys=True))
from probe_cerro_season_companies import capture as season
print('CERRO_SEASON',json.dumps(season(env),sort_keys=True))
env.cr.rollback()
