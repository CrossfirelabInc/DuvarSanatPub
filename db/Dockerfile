FROM postgis/postgis:16-3.4

# Install pgvector extension
# PostgreSQL 16 on Debian was compiled with clang-13, so pgvector's Makefile needs it.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        clang-13 \
        llvm-13 \
        postgresql-server-dev-16 && \
    git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make && make install && \
    cd / && rm -rf /tmp/pgvector && \
    apt-get remove -y build-essential git clang-13 llvm-13 postgresql-server-dev-16 && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*
