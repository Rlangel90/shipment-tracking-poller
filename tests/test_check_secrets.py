from scripts.check_secrets import main, scan_file, scan_text


def test_scan_text_flags_private_key_block():
    problems = scan_text("-----BEGIN RSA PRIVATE KEY-----\nMIIExample\n-----END RSA PRIVATE KEY-----\n")

    assert any("private key" in p for p in problems)


def test_scan_text_allows_placeholder_values():
    problems = scan_text("CARRIER_API_URL=your-key-here\n")

    assert problems == []


def test_scan_text_flags_hardcoded_secret_in_a_snippet():
    problems = scan_text('token = "abcd1234efgh5678"')

    assert any("credential" in p for p in problems)


def test_scan_file_flags_aws_access_key(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("aws_key = AKIAABCDEFGHIJKLMNOP\n")

    problems = scan_file(str(path))

    assert any("AWS" in p for p in problems)


def test_scan_file_allows_placeholder_values(tmp_path):
    path = tmp_path / ".env.example"
    path.write_text("DATABASE_URL=postgresql://user:pw@localhost/db\n")

    problems = scan_file(str(path))

    assert problems == []


def test_scan_file_blocks_committing_a_dot_env_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DATABASE_URL=real\n")

    problems = scan_file(str(path))

    assert any(".env" in p for p in problems)


def test_scan_file_ignores_clean_source(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text("def add(a, b):\n    return a + b\n")

    problems = scan_file(str(path))

    assert problems == []


def test_main_returns_zero_for_clean_files(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text("x = 1\n")

    assert main([str(path)]) == 0


def test_main_returns_one_when_a_file_has_a_problem(tmp_path):
    path = tmp_path / ".env"
    path.write_text("SECRET=whatever\n")

    assert main([str(path)]) == 1
