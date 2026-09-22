"""Unit tests for cache.py. Runs via `cache.sh selftest` or
`python3 -m unittest scripts.test_cache`.

The tests exercise the public CLI through subprocess (via cache.sh) plus a
few white-box helper tests via direct import. Every test sandboxes
KIRO_CACHE_ROOT/HOME/CWD into unrelated temp dirs, then asserts that HOME
and CWD remain empty — the load-bearing check that the cache touches no
filesystem path outside its storage root.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
_CACHE_SH = _SKILL_ROOT / "scripts" / "cache.sh"

# Make cache.py importable for white-box helper tests without polluting
# global state (we restore sys.path after import).
sys.path.insert(0, str(_HERE))
import cache as cache_mod  # noqa: E402
sys.path.pop(0)


class _CacheEnv:
    """Context manager: isolate cache root, HOME, and cwd into temp dirs.

    Exposes .cache (KIRO_CACHE_ROOT), .home, .cwd. On exit, asserts .home
    and .cwd are still empty — proves cache.py did no I/O outside its root.
    """

    def __init__(self, extra_env: dict[str, str] | None = None):
        self._extra = extra_env or {}

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        base = Path(self._td.name)
        self.cache = base / "cache"
        self.home = base / "home"
        self.cwd = base / "cwd"
        for p in (self.cache, self.home, self.cwd):
            p.mkdir()
        self._prev_cwd = os.getcwd()
        os.chdir(self.cwd)
        self._env = os.environ.copy()
        self._env["KIRO_CACHE_ROOT"] = str(self.cache)
        self._env["HOME"] = str(self.home)
        self._env.pop("CACHE_MODE", None)
        self._env.update(self._extra)
        return self

    def __exit__(self, *exc):
        try:
            # Load-bearing assertion — sandbox stayed clean.
            assert list(self.home.iterdir()) == [], (
                f"cache touched HOME: {list(self.home.iterdir())}")
            assert list(self.cwd.iterdir()) == [], (
                f"cache touched CWD: {list(self.cwd.iterdir())}")
        finally:
            os.chdir(self._prev_cwd)
            self._td.cleanup()

    def run(self, *args: str, stdin: bytes | None = None,
            check: bool = True, env_override: dict[str, str] | None = None
            ) -> subprocess.CompletedProcess:
        env = dict(self._env)
        if env_override:
            env.update(env_override)
        proc = subprocess.run(
            [str(_CACHE_SH), *args],
            input=stdin, capture_output=True, env=env,
        )
        if check and proc.returncode != 0:
            raise AssertionError(
                f"cache {' '.join(args)} exited {proc.returncode}: "
                f"stderr={proc.stderr!r}")
        return proc


# ---------------------------------------------------------------- helpers


class TestNamespaceSlug(unittest.TestCase):
    def test_stable_across_invocations(self):
        s1 = cache_mod._namespace_slug("project-overview")
        s2 = cache_mod._namespace_slug("project-overview")
        self.assertEqual(s1, s2)

    def test_sanitize_collisions_still_separate(self):
        # Two inputs that collapse to the same sanitized prefix but differ
        # in raw bytes — the sha256 suffix keeps them apart.
        a = cache_mod._namespace_slug("foo/bar")
        b = cache_mod._namespace_slug("foo-bar")
        self.assertNotEqual(a, b)

    def test_special_chars_produce_safe_folder_name(self):
        slug = cache_mod._namespace_slug("hello world / colon:α")
        # Must contain only [A-Za-z0-9_.-]
        self.assertRegex(slug, r"^[A-Za-z0-9_.-]+$")
        self.assertGreater(len(slug), 8)

    def test_empty_namespace_rejected(self):
        with self.assertRaises(SystemExit):
            cache_mod._namespace_slug("")

    def test_all_special_falls_back_to_hash_only(self):
        # A namespace of only special chars still yields a slug that ends
        # in the 8-hex suffix (via the "ns" fallback).
        slug = cache_mod._namespace_slug("///:::")
        self.assertRegex(slug, r"^ns-[0-9a-f]{8}$")


class TestFragmentHash(unittest.TestCase):
    def test_stable_ordered(self):
        a = cache_mod._fragment_hash(["a", "b", "c"])
        b = cache_mod._fragment_hash(["a", "b", "c"])
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)

    def test_reorder_flips_digest(self):
        a = cache_mod._fragment_hash(["a", "b"])
        b = cache_mod._fragment_hash(["b", "a"])
        self.assertNotEqual(a, b)

    def test_added_part_changes_digest(self):
        a = cache_mod._fragment_hash(["a", "b"])
        b = cache_mod._fragment_hash(["a", "b", ""])
        self.assertNotEqual(a, b)

    def test_null_separator_disambiguates(self):
        # ("ab","c") vs ("a","bc") — without the NUL separator these would
        # collide.
        a = cache_mod._fragment_hash(["ab", "c"])
        b = cache_mod._fragment_hash(["a", "bc"])
        self.assertNotEqual(a, b)


# ---------------------------------------------------------------- CLI: key


class TestKeyCommand(unittest.TestCase):
    def test_prefix_format(self):
        with _CacheEnv() as env:
            out = env.run("key", "--namespace", "proj",
                          "--part", "head", "--part", "v1").stdout.decode()
            prefix = out.strip()
            slug, frag = prefix.split("/")
            self.assertRegex(slug, r"^proj-[0-9a-f]{8}$")
            self.assertRegex(frag, r"^[0-9a-f]{24}$")

    def test_no_parts_stable(self):
        with _CacheEnv() as env:
            a = env.run("key", "--namespace", "x").stdout
            b = env.run("key", "--namespace", "x").stdout
            self.assertEqual(a, b)


# ---------------------------------------------------------------- CLI: set/get/del


class TestSetGetRoundtrip(unittest.TestCase):
    def test_shallow_key(self):
        with _CacheEnv() as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            key = f"{prefix}/doc"
            env.run("set", key, stdin=b"value: 1\n")
            got = env.run("get", key).stdout
            self.assertEqual(got, b"value: 1\n")

    def test_deeply_nested_key(self):
        with _CacheEnv() as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            key = f"{prefix}/a/b/c/deep-doc"
            env.run("set", key, stdin=b"nested: yes")
            self.assertEqual(env.run("get", key).stdout, b"nested: yes")

    def test_miss_returns_empty(self):
        with _CacheEnv() as env:
            got = env.run("get", "ns-deadbeef/frag/missing").stdout
            self.assertEqual(got, b"")

    def test_dot_in_key_appends_suffix(self):
        with _CacheEnv() as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            key = f"{prefix}/foo.bar"
            env.run("set", key, stdin=b"payload")
            # The on-disk file has BOTH dots preserved plus the .yaml suffix.
            path = env.cache / f"{key}.yaml"
            self.assertTrue(path.is_file())
            self.assertEqual(env.run("get", key).stdout, b"payload")


class TestDelete(unittest.TestCase):
    def test_missing_key_exits_zero(self):
        with _CacheEnv() as env:
            proc = env.run("del", "ns-cafecafe/frag/nope", check=False)
            self.assertEqual(proc.returncode, 0)


# ---------------------------------------------------------------- CLI: list


class TestList(unittest.TestCase):
    def test_sorted_keys(self):
        with _CacheEnv() as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            for name in ("gamma", "alpha", "beta"):
                env.run("set", f"{prefix}/{name}", stdin=b"x")
            out = env.run("list", prefix).stdout.decode().strip().splitlines()
            self.assertEqual(out, sorted(out))
            self.assertEqual(
                [k.rsplit("/", 1)[-1] for k in out],
                ["alpha", "beta", "gamma"],
            )

    def test_empty_prefix_no_output(self):
        with _CacheEnv() as env:
            proc = env.run("list", "ns-nothing/frag")
            self.assertEqual(proc.stdout, b"")

    def test_descends_nested_prefixes(self):
        with _CacheEnv() as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            env.run("set", f"{prefix}/deep/nested/leaf", stdin=b"x")
            env.run("set", f"{prefix}/shallow", stdin=b"x")
            out = env.run("list", prefix).stdout.decode().strip().splitlines()
            self.assertIn(f"{prefix}/deep/nested/leaf", out)
            self.assertIn(f"{prefix}/shallow", out)


# ---------------------------------------------------------------- mode gating


class TestModeGating(unittest.TestCase):
    def _prep(self, env):
        prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
        key = f"{prefix}/doc"
        env.run("set", key, stdin=b"seed")
        return key

    def test_read_only_blocks_set_and_del(self):
        with _CacheEnv() as env:
            key = self._prep(env)
            env.run("set", key, "--mode", "read-only", stdin=b"new")
            self.assertEqual(env.run("get", key).stdout, b"seed")
            env.run("del", key, "--mode", "read-only")
            self.assertEqual(env.run("get", key).stdout, b"seed")

    def test_write_only_blocks_get(self):
        with _CacheEnv() as env:
            key = self._prep(env)
            self.assertEqual(
                env.run("get", key, "--mode", "write-only").stdout, b"")

    def test_bypass_noops_all_three(self):
        with _CacheEnv() as env:
            key = self._prep(env)
            env.run("set", key, "--mode", "bypass", stdin=b"attempt")
            self.assertEqual(env.run("get", key).stdout, b"seed")
            self.assertEqual(
                env.run("get", key, "--mode", "bypass").stdout, b"")
            env.run("del", key, "--mode", "bypass")
            self.assertEqual(env.run("get", key).stdout, b"seed")

    def test_cache_mode_env_honored(self):
        with _CacheEnv(extra_env={"CACHE_MODE": "read-only"}) as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            key = f"{prefix}/doc"
            env.run("set", key, stdin=b"blocked-by-env")
            # The set was gated to no-op because CACHE_MODE=read-only.
            self.assertEqual(env.run("get", key).stdout, b"")

    def test_flag_overrides_env(self):
        with _CacheEnv(extra_env={"CACHE_MODE": "read-only"}) as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            key = f"{prefix}/doc"
            env.run("set", key, "--mode", "read-write", stdin=b"written")
            self.assertEqual(env.run("get", key).stdout, b"written")

    def test_unknown_mode_exits_nonzero(self):
        with _CacheEnv(extra_env={"CACHE_MODE": "gibberish"}) as env:
            prefix = env.run("key", "--namespace", "n").stdout.decode().strip()
            key = f"{prefix}/doc"
            proc = env.run("set", key, stdin=b"x", check=False)
            self.assertNotEqual(proc.returncode, 0)


class TestGCLru(unittest.TestCase):
    def test_keeps_n_most_recent_prefixes(self):
        with _CacheEnv() as env:
            slug = cache_mod._namespace_slug("n")
            ns_dir = env.cache / slug
            ns_dir.mkdir(parents=True)
            # Create 5 prefix dirs with increasing mtime.
            now = time.time()
            for i in range(5):
                frag = ns_dir / f"frag{i:02d}"
                frag.mkdir()
                doc = frag / "doc.yaml"
                doc.write_text(f"i: {i}")
                stamp = now - (5 - i) * 3600
                os.utime(doc, (stamp, stamp))
                os.utime(frag, (stamp, stamp))
            env.run("gc", "--namespace", "n", "--keep-keys", "2")
            remaining = sorted(p.name for p in ns_dir.iterdir()
                               if p.is_dir())
            self.assertEqual(remaining, ["frag03", "frag04"])


class TestGCFlock(unittest.TestCase):
    def test_returns_zero_under_contention(self):
        import fcntl
        with _CacheEnv() as env:
            slug = cache_mod._namespace_slug("n")
            ns_dir = env.cache / slug
            ns_dir.mkdir(parents=True)
            lock_path = ns_dir / ".gc.lock"
            fh = open(lock_path, "a+")
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                proc = env.run("gc", "--namespace", "n", check=False)
                self.assertEqual(proc.returncode, 0)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
                fh.close()


# ---------------------------------------------------------------- traversal


class TestTraversalDefense(unittest.TestCase):
    def test_dotdot_in_get_rejected(self):
        with _CacheEnv() as env:
            proc = env.run("get", "../escape", check=False)
            self.assertNotEqual(proc.returncode, 0)

    def test_dotdot_in_set_rejected(self):
        with _CacheEnv() as env:
            proc = env.run("set", "with/../evil", stdin=b"x", check=False)
            self.assertNotEqual(proc.returncode, 0)

    def test_absolute_key_rejected(self):
        with _CacheEnv() as env:
            proc = env.run("set", "/etc/passwd", stdin=b"x", check=False)
            self.assertNotEqual(proc.returncode, 0)


class TestSelftest(unittest.TestCase):
    """Meta-test: the selftest subcommand must be callable. We only smoke it
    (not recurse into itself) by asserting the parser routes it — actual run
    happens via cache.sh selftest which is what invokes this test module.
    """
    def test_selftest_subcommand_parses(self):
        parser = cache_mod._build_parser()
        args = parser.parse_args(["selftest"])
        self.assertEqual(args.command, "selftest")


if __name__ == "__main__":
    unittest.main()
