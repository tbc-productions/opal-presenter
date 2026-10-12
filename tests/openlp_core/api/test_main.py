# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################

from flask import Flask
import pytest

from opal.core.api.main import AppLocation, get_mime_type, main_views


@pytest.fixture
def remote_client(tmp_path, monkeypatch):
    for section in ('remotes', 'stages'):
        (tmp_path / section).mkdir()
    (tmp_path / 'remotes/index.html').write_text('remote index')
    (tmp_path / 'remotes/client.js').write_text('remote script')
    (tmp_path / 'stages/custom/nested').mkdir(parents=True)
    (tmp_path / 'stages/custom/stage.html').write_text('custom stage')
    (tmp_path / 'stages/custom/nested/stage.css').write_text('custom asset')
    (tmp_path / 'stage.html').write_text('private stage')
    (tmp_path / 'private.txt').write_text('private data')
    monkeypatch.setattr(AppLocation, 'get_section_data_path', lambda section: tmp_path / section)
    app = Flask(__name__)
    app.register_blueprint(main_views)
    return app.test_client()


@pytest.mark.parametrize('url,expected', [
    ('/', 'remote index'), ('/missing', 'remote index'), ('/client.js', 'remote script'),
    ('/stage/custom/', 'custom stage'), ('/stage/custom/nested/stage.css', 'custom asset')
])
def test_remote_files(remote_client, url, expected):
    response = remote_client.get(url)
    assert response.status_code == 200
    assert response.get_data(as_text=True) == expected


@pytest.mark.parametrize('url', [
    '/stage/../', '/stage/%2e%2e/private.txt', '/stage/custom/../../private.txt',
    '/stage/missing/', '/stage/custom/missing.css'
])
def test_stage_paths_stay_in_stage_directory(remote_client, url):
    assert remote_client.get(url).status_code == 404


def test_index_traversal_returns_only_public_index(remote_client):
    response = remote_client.get('/..%5cprivate.txt')
    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'remote index'


def test_get_mime_type():
    assert get_mime_type('index.html') == 'text/html'
    assert get_mime_type('stage.js') == 'application/javascript'
    assert get_mime_type('stage.css') == 'text/css'
