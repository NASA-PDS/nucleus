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
# Builder stage -- compiles funpack from source. Everything installed
# here (the full 'Development Tools' toolchain, kernel-headers, make,
# tar, etc.) stays in this stage only. An Inspector scan of the old
# single-stage build found 614 High findings here, 458 of them just
# kernel-headers -- none of that is needed to actually run this image,
# only to build funpack once. Splitting into a builder stage drops the
# whole toolchain (and its CVEs) from the final image.
# -----------------------------------------------------------------------
FROM public.ecr.aws/amazonlinux/amazonlinux:latest AS builder

RUN yum -y update \
    && yum -y install make tar \
    && yum -y groupinstall 'Development Tools' \
    && yum -y clean all

ENV CFITSIO_IMAGE_PATH https://heasarc.gsfc.nasa.gov/FTP/software/fitsio/c/cfitsio-4.4.0.tar.gz
ADD $CFITSIO_IMAGE_PATH cfitsio-4.4.0.tar.gz
RUN tar xvf cfitsio-4.4.0.tar.gz && cd /cfitsio-4.4.0 && ./configure && make && make install && make funpack

# -----------------------------------------------------------------------
# awscli builder stage -- same reasoning as the final stage below: AL2023's
# yum/unzip/curl are only needed to install awscli, not to run it.
# -----------------------------------------------------------------------
FROM public.ecr.aws/amazonlinux/amazonlinux:latest AS aws-builder

RUN yum -y update \
    && yum -y install unzip \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && /aws/install \
    && rm -rf aws*

# -----------------------------------------------------------------------
# Final stage -- debian-slim instead of AL2023: no yum/dnf/rpm, so the
# rpm*/python3*/openssl-fips-provider CVE set tied to AL2023's package
# manager (confirmed un-removable via `yum remove`, see git history) isn't
# present at all, not just patched. glibc-compatible, so both the
# glibc-linked awscli binaries and the glibc-linked funpack binary (built
# against AL2023's glibc in the builder stage above) run fine here. Only
# what's needed at runtime: awscli, libbrotli1/zlib1g (funpack's runtime
# deps), the compiled funpack binary + its shared libs, and the entrypoint
# script.
#
# Dropped findings from 1527 (234 High) to 19 (2 High). The 2 remaining
# High findings (CVE-2026-5435, CVE-2026-19499) are both in glibc,
# confirmed via Inspector as fixAvailable: NO / fixedInVersion:
# NotAvailable -- there's no patched glibc upstream yet for Debian stable,
# for anyone, not just us. Same as config-init's Dockerfile: glibc isn't
# removable, every binary here (bash, aws CLI, funpack) links against it.
# Left as-is; revisit once Debian ships a fix.
# -----------------------------------------------------------------------
FROM debian:stable-slim

RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends libbrotli1 zlib1g \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=aws-builder /usr/local/aws-cli /usr/local/aws-cli
COPY --from=aws-builder /usr/local/bin/aws /usr/local/bin/aws
COPY --from=aws-builder /usr/local/bin/aws_completer /usr/local/bin/aws_completer

COPY --from=builder /cfitsio-4.4.0/funpack /cfitsio-4.4.0/funpack
COPY --from=builder /cfitsio-4.4.0/lib /cfitsio-4.4.0/lib

ENV PATH="$PATH:/cfitsio-4.4.0"
ENV LD_LIBRARY_PATH="/cfitsio-4.4.0/lib"

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["bash", "/usr/local/bin/entrypoint.sh"]
