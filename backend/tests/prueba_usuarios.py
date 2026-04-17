def test_register_login_me_round_trip(client, registered_user):
    # Login with the credentials just registered
    login = client.post(
        "/api/v1/users/login",
        data={"username": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert token

    # /me with the bearer token
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == registered_user["email"]


def test_me_does_not_leak_hashed_password(client, registered_user):
    """Security: /me must never expose the bcrypt hash."""
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {registered_user['token']}"},
    )
    assert me.status_code == 200
    assert "hashed_password" not in me.json()


def test_register_rejects_duplicate_email(client, registered_user):
    dup = client.post(
        "/api/v1/users/register",
        json={"name": "Other", "email": registered_user["email"], "password": "whatever"},
    )
    assert dup.status_code == 400
