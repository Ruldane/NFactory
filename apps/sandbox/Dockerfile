# NFactory code sandbox (ADR-0005). Build context: repository root.
# Runs recipe checks for the worker. No Internet: it sits on an internal-only network,
# so every tool a generated project needs is installed here, at build time, pinned.
FROM python:3.13-slim

# Pinned toolchains; downloads are checked against these digests.
ARG PWSH_VERSION=7.6.9
ARG PWSH_SHA256=1da6d6d6035d651f20e70ddee7c4c15ac6ab8b9fb40ee92240d91263f28a884b
ARG NODE_VERSION=24.22.2
ARG NODE_SHA256=48cc0e21e048790e54c0cf5749c2725005313d652651c40b7a21feb9697aaf75
ARG PESTER_VERSION=6.2.0
ARG PSSA_VERSION=1.25.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POWERSHELL_TELEMETRY_OPTOUT=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    NFACTORY_WEB_DEPS=/opt/nfactory/web-deps/node_modules \
    HOME=/tmp

# PowerShell 7 (powershell-automation) and Node.js (webapp-react-fastapi).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl xz-utils libicu76 \
    && curl -fsSL -o /tmp/pwsh.tgz \
       "https://github.com/PowerShell/PowerShell/releases/download/v${PWSH_VERSION}/powershell-${PWSH_VERSION}-linux-x64.tar.gz" \
    && echo "${PWSH_SHA256}  /tmp/pwsh.tgz" | sha256sum -c - \
    && mkdir -p /opt/microsoft/powershell/7 \
    && tar -xzf /tmp/pwsh.tgz -C /opt/microsoft/powershell/7 \
    && chmod +x /opt/microsoft/powershell/7/pwsh \
    && ln -s /opt/microsoft/powershell/7/pwsh /usr/local/bin/pwsh \
    && curl -fsSL -o /tmp/node.txz \
       "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && echo "${NODE_SHA256}  /tmp/node.txz" | sha256sum -c - \
    && tar -xJf /tmp/node.txz -C /usr/local --strip-components=1 \
       --exclude="*/include" --exclude="*/share" --exclude="*.md" \
    && rm /tmp/pwsh.tgz /tmp/node.txz \
    && apt-get purge -y curl xz-utils && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Pester and PSScriptAnalyzer, for every user, from the PowerShell Gallery.
# The versions are expanded by sh; any PowerShell error fails the build.
RUN pwsh -NoProfile -NonInteractive -Command \
    "\$ErrorActionPreference = 'Stop'; \
     Set-PSRepository PSGallery -InstallationPolicy Trusted; \
     Install-Module Pester -RequiredVersion ${PESTER_VERSION} -Scope AllUsers -Force -SkipPublisherCheck; \
     Install-Module PSScriptAnalyzer -RequiredVersion ${PSSA_VERSION} -Scope AllUsers -Force; \
     Import-Module Pester, PSScriptAnalyzer" \
    && rm -rf /tmp/* /tmp/.[!.]*

# Python libraries the generated projects use.
COPY apps/sandbox/requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt

# Frontend toolchain the generated web apps link to (they pin the same versions).
COPY apps/sandbox/web-deps/package.json apps/sandbox/web-deps/package-lock.json /opt/nfactory/web-deps/
RUN cd /opt/nfactory/web-deps && npm ci --no-audit --no-fund && npm cache clean --force \
    && rm -rf /tmp/* /tmp/.[!.]*

COPY apps/sandbox/nfactory_sandbox /srv/nfactory_sandbox

# Same uid as the worker: both write into the shared per-run workspaces.
RUN useradd --uid 10001 --no-create-home sandbox \
    && mkdir -p /data/workspaces \
    && chown sandbox /data/workspaces
USER sandbox
WORKDIR /srv
EXPOSE 8800
# The supervisor (compose.yaml). Run containers replace the command with a recipe check.
CMD ["python", "-m", "nfactory_sandbox"]
