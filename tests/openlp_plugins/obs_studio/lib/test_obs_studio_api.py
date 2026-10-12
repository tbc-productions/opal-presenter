from opal.plugins.obs_studio.lib.obs_studio_api import ObsStudioAPI


def test_authentication_matches_obs_challenge_response_protocol():
    api = ObsStudioAPI.__new__(ObsStudioAPI)
    api._ObsStudioAPI__password = 'supersecretpassword'
    salt = 'lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI='
    challenge = '+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY='
    assert api._ObsStudioAPI__build_auth_string(salt, challenge) == '1Ct943GAT+6YQUUX47Ia/ncufilbe6+oD6lY+5kaCu4='
