**English** | [Tiếng Việt](../vn/cli.md)

# Command-line tools

```bash
xime init <project-name>     # create the project tree and its basic files
xime config --print          # print every configuration key with its default
xime check config            # compare your application.yml against it
xime check module-level      # catch non-deterministic calls at module level
xime grpc generate|check|client
```

---

## Configuration lives in TWO places, and the line is not arbitrary

| | Where | Who decides |
|---|---|---|
| **Operational** - ports, connection strings, paths, limits | `resources/application.yml` | the operator |
| **Architecture** - DI bindings, routing, middleware, CORS, event bus ceiling | `config/*.py` | the developer |

The question that sorts them: **does an operator have the information needed to
choose this value?** If not it belongs in `config/*.py`, even when it is a number
and even when it sounds operational.

---

## `xime config --print`

Prints the framework's **whole** configuration surface to stdout: every block,
every key, its default, and an explanation. It writes nothing.

```bash
xime config --print > resources/application.yml     # start a new file
xime config --print | diff - resources/application.yml   # compare with yours
```

### ⭐ The split rule: comment what can be defaulted, write out what cannot

```yaml
lmdb:
  path: /dev/shm/orders-store     # the framework cannot guess it -> written out
  # map_size: 64MB                # a framework default -> leave it commented
  # total_max: 1GiB
```

Reading the file then tells you at a glance: **an uncommented line is something
this deployment actually decided**; a commented line is documentation, and if it
ages it harms nobody because it is inert.

⚠ **Do not copy a default out of its comment unless you mean to change it.** A
value written into the file **freezes that behaviour at the version the file was
created with**: a later Xime release that changes the default for a security
reason will never reach you.

### Why `lmdb.path` has no default

Several Xime services share one machine, and the store **deliberately survives a
restart**, so its name has to be stable. A stable default would therefore be the
**same directory for every app on the box** - two services overwriting each
other's rate-limit tables, **with nothing to hint at it**. The framework refuses
to guess; the generator can, because it knows the project name.

⭐ The general line: **the framework may guess when guessing wrong makes a
noise** (two apps on port 8080 -> `EADDRINUSE`, dead at startup), **and may not
when guessing wrong is silent**.

---

## `xime check config`

Compares your `application.yml` against that surface. What it catches that
nothing else does today: **misspelled keys**.

```text
  server.prot: unknown key   did you mean 'port'?
  lmdb.path: required key is missing

2 problem(s) in /srv/orders/resources/application.yml.
Blocks checked: server, lmdb
```

**Three exit codes:** `0` clean · `1` problems · `2` **inconclusive** (the file
could not be read). Code `2` exists because *"found no problem"* and *"could not
read it to look"* are different answers.

⚠ **It deliberately does not police everything.** Blocks belonging to your own
application (`trust:`, `app:`) and blocks the framework does not fully describe
are left alone. A probe that flags valid keys gets turned off in its first week,
and then it catches nothing at all. The `Blocks checked:` line says what it
really looked at.

### A misspelt BLOCK name gets a suggestion too

```text
  serber: unknown block   did you mean 'server'?
```

This is the same typo as `server.porrt`, one level up - and the same
consequence: the application runs on the **framework default**, the operator
believes it is running on the value they just wrote, and no log line says
otherwise.

⭐ **A suggestion appears only when the unknown name is CLOSE to a known one**,
and stays silent when it is not. Measured against real Xime `application.yml`
files: `serber`, `sever`, `grcp` and `procss` are all caught, while `trust`,
`app`, `shard`, `legal` and `organization` produce **not one false positive**.

---

## `xime init`

```bash
xime init orders
cd orders && pip install -e . && python main.py
```

It generates **little**, on purpose: `main.py`, `config/`, a sample controller,
the two configuration files, `pyproject.toml`, `.gitignore`, `README.md`. It does
not lay out `application/service/` or `infrastructure/repository/` for you -
architecture is your call, and every generated file is one the framework
implicitly owns forever.

Two configuration files, two different jobs:

| | |
|---|---|
| `application.yml` | the real one, **fully commented**, kept out of git (secrets) |
| `application.yml.example` | for git, **no comments**, required keys only |

⚠ The `.example` only exists so a fresh clone knows what to fill in - **deleting
it is fine**. Every explanation lives in `xime config --print`, which never goes
stale; comments inside a file tracked by git are documentation that ages in
silence.

⛔ The command **refuses to overwrite** existing files. Overwriting a live
`application.yml` erases a real deployment's configuration and there is no way
back. Pass `--force` when that is what you want.

### A few names are rejected, and the reason is worth reading

```bash
xime init config
#   Detail: 'config' is reserved: the generated project already has a 'config'
#           of its own, and the two would overwrite each other
```

The generator creates `config/` and `resources/` itself, while the project name
becomes the Python package name. If they collide, two templates write to **the
same file** and the later one wins - the project ends up missing exactly
`config/__init__.py`, where `import dependency` lives. Nothing fails at creation
time; it fails at run time, with a message unrelated to the name.

`xime init xime` is worse still: the project package **shadows the framework**.

Rejected: `config`, `resources`, `xime`, `main`, `test`, `tests`, and any name
matching a **Python standard library** module (`json`, `socket`, `logging`, ...).

### A new project listens on `127.0.0.1`, not `0.0.0.0`

The generated `application.yml` opens the `server:` block with
`host: "127.0.0.1"` and explains it in place. The **framework** default is still
`0.0.0.0` and does not change - `xime config --print` still prints it that way,
and running applications are unaffected because they do not re-run the generator.

Why: `0.0.0.0` means **every network interface** - anyone who can route to this
machine can call it. That is the right answer inside a container and the wrong
one on a laptop or a shared box. The generator starts you on the narrow side;
widening it is a deliberate decision rather than a default you did not know you
had accepted.

---

## `xime check module-level`

See [Multi-process](multi-process.md), section *"Module-level code runs `N+1`
times"*.

---

## Related

- [Configuration](configuration.md) - the two config tiers and how they load.
- [Multi-process](multi-process.md) - `share_load()`, and the first probe.
- [Store](store.md) - the inter-process store, and why `lmdb.path` is required.

---

[← Configuration](configuration.md) · **CLI** · [Testing →](testing.md)
