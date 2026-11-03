"""NFactory sandbox supervisor (ADR-0005 v2).

Interface: `server.make_server` / `server.Config` (HTTP), `containers.ContainerExecutor`
(one confined container per command), `engine.DockerEngine` (Docker Engine client).
Run with `python -m nfactory_sandbox`.
"""
