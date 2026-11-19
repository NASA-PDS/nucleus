# Copyright 2024, California Institute of Technology ("Caltech").
# U.S. Government sponsorship acknowledged.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other
# materials provided with the distribution.
# * Neither the name of Caltech nor its operating division, the Jet Propulsion
# Laboratory, nor the names of its contributors may be used to endorse or
# promote products derived from this software without specific prior written
# permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# -----------------------------------------------------------------------
# Builder stage -- installs awscli using the full AL2023 toolchain
# (yum/unzip/curl). None of that -- nor the rpm*/python3*/dnf stack that
# comes with it -- is needed at runtime; only the installed
# /usr/local/aws-cli tree and the /usr/local/bin/aws launcher are. AL2023's
# python3/rpm are hard dependencies of dnf itself (confirmed: `yum remove
# python3` silently no-ops rather than actually removing it), so the only
# way to drop those CVEs from the shipped image is to not ship an
# RPM-based final stage at all.
# -----------------------------------------------------------------------
FROM public.ecr.aws/amazonlinux/amazonlinux:latest AS builder

RUN yum -y update \
    && yum -y install unzip \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && /aws/install \
    && rm -rf aws*

# -----------------------------------------------------------------------
# Final stage -- debian-slim: has bash (entrypoint.sh needs it) and glibc
# (awscli v2's binaries are glibc-linked, so an Alpine/musl base won't
# run them), but no yum/dnf/rpm -- the package-manager-tied CVE set
# (openssl-fips-provider, rpm*, pcre2, curl-minimal, libcap, krb5-libs,
# python3*: 54 High findings on the old single-stage AL2023 image) isn't
# present here at all, not just patched.
# -----------------------------------------------------------------------
FROM debian:stable-slim

# Dropped findings from 195 (56 High) to 19 (2 High). The 2 remaining High
# findings (CVE-2026-5435, CVE-2026-19499) are both in glibc, confirmed
# via Inspector as fixAvailable: NO / fixedInVersion: NotAvailable --
# there's no patched glibc upstream yet for Debian stable, for anyone, not
# just us. glibc is also not something that can be removed -- every
# binary in this image (bash, aws CLI, coreutils) links against it, same
# category of problem as AL2023's python3/dnf coupling above. Left as-is;
# revisit once Debian ships a fix.
RUN apt-get update && apt-get -y upgrade && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/aws-cli /usr/local/aws-cli
COPY --from=builder /usr/local/bin/aws /usr/local/bin/aws
COPY --from=builder /usr/local/bin/aws_completer /usr/local/bin/aws_completer

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["bash", "/usr/local/bin/entrypoint.sh"]
