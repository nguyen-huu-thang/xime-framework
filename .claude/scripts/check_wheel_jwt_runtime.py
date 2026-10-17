"""Install only wheel[jwt] into fresh venvs and exercise every advertised key family.

Run with the dev environment (cryptography generates synthetic test vectors):
  python .claude/scripts/check_wheel_jwt_runtime.py --wheel <wheel> --output <new-temp-dir>

The output directory must not exist. It contains venvs, installation logs and
synthetic keys; no existing environment or application configuration is changed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path

_SMOKE = '''
import json,sys,sysconfig
from importlib.metadata import PackageNotFoundError,version
from pathlib import Path
import xime
from xime.core.exception import AuthenticationException
from xime.starters.jwt import KeyContext,PyJwtTokenSigner,PyJwtTokenVerifier
from xime.cli._config_check import check

assert Path(xime.__file__).resolve().is_relative_to(Path(sysconfig.get_paths()["purelib"]).resolve())
fixtures=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
secret="synthetic-wheel-parser-password"
bad_yaml=Path(sys.argv[1]).parent/"malformed-credential.yml"
bad_yaml.write_text('webserver:\\n  ssl:\\n    keyfile_password: "'+secret+'\\n',encoding="utf-8")
checked=check(bad_yaml)
assert checked.verdict=="inconclusive" and secret not in repr(checked)
results=[]
for fixture in fixtures:
    context=KeyContext(**fixture["key"])
    try:
        verifier=PyJwtTokenVerifier()
        def verify(token):
            return verifier.verify(token,context,audience="wheel-audience",issuer="wheel-issuer",require=["exp"])
        assert verify(fixture["reference"])["sub"]=="wheel-example"
        signed=PyJwtTokenSigner().sign(fixture["payload"],context)
        assert verify(signed)["sub"]=="wheel-example"
        header,payload,signature=signed.split(".")
        corrupted=("A" if signature[0]!="A" else "B")+signature[1:]
        try:
            verify(header+"."+payload+"."+corrupted)
        except AuthenticationException:
            pass
        else:
            raise AssertionError("corrupted signature was accepted")
    except Exception as error:
        results.append({"case":fixture["case"],"ok":False,"error":type(error).__name__})
    else:
        results.append({"case":fixture["case"],"ok":True})
versions={}
for package in ("pyjwt","cryptography"):
    try:versions[package]=version(package)
    except PackageNotFoundError:versions[package]=None
print(json.dumps({"xime_file":xime.__file__,"versions":versions,"yaml_redaction":True,"cases":results}))
raise SystemExit(int(any(not row["ok"] for row in results)))
'''


def _vectors() -> list[dict]:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa

    private_keys = {
        "rsa": rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "ES256": ec.generate_private_key(ec.SECP256R1()),
        "ES256K": ec.generate_private_key(ec.SECP256K1()),
        "ES384": ec.generate_private_key(ec.SECP384R1()),
        "ES512": ec.generate_private_key(ec.SECP521R1()),
        "Ed25519": ed25519.Ed25519PrivateKey.generate(),
        "Ed448": ed448.Ed448PrivateKey.generate(),
    }
    payload = {"sub": "wheel-example", "aud": "wheel-audience", "iss": "wheel-issuer",
               "exp": int(time.time()) + 3600}
    cases = []
    for algorithm in ("HS256", "HS384", "HS512", "RS256", "RS384", "RS512",
                      "PS256", "PS384", "PS512", "ES256", "ES256K", "ES384", "ES512",
                      "Ed25519", "Ed448"):
        if algorithm.startswith("HS"):
            key = {"algorithm": algorithm, "secret": "wheel-test-key-" * 8}
            material = key["secret"]
        else:
            private = private_keys["rsa" if algorithm.startswith(("RS", "PS")) else algorithm]
            key = {
                "algorithm": "EdDSA" if algorithm.startswith("Ed") else algorithm,
                "private_key_pem": private.private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ).decode(),
                "public_key_pem": private.public_key().public_bytes(
                    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode(),
            }
            material = key["private_key_pem"]
        cases.append({"case": algorithm, "payload": payload, "key": key,
                      "reference": jwt.encode(payload, material, algorithm=key["algorithm"])})
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        parser.error("--wheel must name a wheel file")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    vectors = output / "synthetic-vectors.json"
    vectors.write_text(json.dumps(_vectors()), encoding="utf-8")
    smoke = output / "smoke.py"
    smoke.write_text(_SMOKE, encoding="utf-8")
    project = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    jwt_floors = []
    for requirement in project["optional-dependencies"]["jwt"]:
        package, floor = requirement.split(">=", 1)
        jwt_floors.append(package.split("[", 1)[0] + "==" + floor)
    constraints = output / "jwt-floors.txt"
    constraints.write_text("\n".join(jwt_floors) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_CACHE_DIR"] = str(output / "pip-cache")
    rows = []
    for label in ("resolver", "jwt-floors"):
        venv = output / label
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, env=env)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = [str(python), "-m", "pip", "install", f"{wheel}[jwt]"]
        if label == "jwt-floors":
            command.extend(["--constraint", str(constraints)])
        with (output / f"{label}-install.log").open("w", encoding="utf-8") as stream:
            installed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                       cwd=output, env=env, timeout=300)
        if installed.returncode:
            row = {"environment": label, "install_exit": installed.returncode}
        else:
            checked = subprocess.run([str(python), "-m", "pip", "check"], env=env,
                                     cwd=output, capture_output=True, text=True, timeout=30)
            result = subprocess.run([str(python), "-I", str(smoke), str(vectors)], env=env,
                                    cwd=output, capture_output=True, text=True, timeout=30)
            row = {"environment": label, "install_exit": 0, "pip_check_exit": checked.returncode,
                   "smoke_exit": result.returncode}
            try:
                row.update(json.loads(result.stdout))
                cases = row.get("cases", [])
                if (row.get("yaml_redaction") is not True or len(cases) != 15 or {case.get("case") for case in cases}
                        != {case["case"] for case in json.loads(vectors.read_text(encoding="utf-8"))}
                        or any(case.get("ok") is not True for case in cases)):
                    row["smoke_exit"] = 1
            except json.JSONDecodeError:
                # Never dump fixture keys or raw decoder output into the report.
                row["smoke_error"] = "child did not produce a JSON result"
                row["smoke_exit"] = 1
        rows.append(row)
        (output / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps(row), flush=True)
    return int(any(row["install_exit"] or row.get("pip_check_exit") or row.get("smoke_exit")
                   for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
