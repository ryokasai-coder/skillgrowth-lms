"""Skill Growth 管理者（role=skillgrowth）の追加・編集。"""
from werkzeug.security import generate_password_hash

from conftest import flask_app, db, User, Company, login


def _admin(username='sg', role='skillgrowth', company_id=None):
    with flask_app.app_context():
        u = User(username=username, email=f'{username}@example.com',
                 password_hash=generate_password_hash('pass1234'),
                 role=role, full_name=username, company_id=company_id)
        db.session.add(u)
        db.session.commit()
        return u.id


def _form(**kw):
    d = {'username': 'newadmin', 'email': 'newadmin@example.com', 'password': 'longpass1',
         'full_name': '新管理者', 'role': 'skillgrowth'}
    d.update(kw)
    return d


def _user(username):
    with flask_app.app_context():
        u = User.query.filter_by(username=username).first()
        return None if u is None else (u.role, u.company_id, u.force_password_change)


def test_admin_can_create_skillgrowth_admin(client):
    _admin()
    with flask_app.app_context():
        c = Company(name='A社')
        db.session.add(c)
        db.session.commit()
        cid = c.id
    login(client, 'sg')
    client.post('/admin/users/new', data=_form(company_id=str(cid)))
    role, company_id, force = _user('newadmin')
    assert role == 'skillgrowth'
    assert company_id is None      # 管理者は会社に属さない
    assert force is True           # 初回ログインでPW変更を強制


def test_new_user_rejects_short_password(client):
    _admin()
    login(client, 'sg')
    client.post('/admin/users/new', data=_form(password='short'))
    assert _user('newadmin') is None


def test_admin_list_shows_skillgrowth_admins(client):
    _admin()
    _admin('sg2')
    login(client, 'sg')
    html = client.get('/admin/users').get_data(as_text=True)
    assert 'sg2' in html and 'Skill Growth管理者' in html


def test_company_admin_cannot_create_admin(client):
    with flask_app.app_context():
        c = Company(name='A社')
        db.session.add(c)
        db.session.commit()
        cid = c.id
    _admin('caa', role='company_admin', company_id=cid)
    login(client, 'caa')
    client.post('/admin/users/new', data=_form())
    assert _user('newadmin') is None


def test_cannot_demote_self(client):
    uid = _admin()
    _admin('sg2')
    login(client, 'sg')
    client.post(f'/admin/users/{uid}/edit', data={'full_name': 'sg', 'email': 'sg@example.com',
                                                   'role': 'employee'})
    assert _user('sg')[0] == 'skillgrowth'


def test_can_demote_other_admin(client):
    _admin()
    uid2 = _admin('sg2')
    login(client, 'sg')
    client.post(f'/admin/users/{uid2}/edit', data={'full_name': 'sg2', 'email': 'sg2@example.com',
                                                    'role': 'employee'})
    assert _user('sg2')[0] == 'employee'
