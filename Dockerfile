FROM node:22-bookworm AS node
FROM ubuntu:22.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git build-essential pkg-config tmux libevent-dev libncurses-dev libwebkit2gtk-4.1-dev libssl-dev librsvg2-dev libxdo-dev libdbus-1-dev && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/ /usr/local/
ENV PATH="/root/.cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup.sh && sh /tmp/rustup.sh -y --profile minimal
RUN curl -fL --retry 3 https://github.com/tmux/tmux/releases/download/2.7/tmux-2.7.tar.gz -o /tmp/tmux.tar.gz && tar -xzf /tmp/tmux.tar.gz -C /tmp && cd /tmp/tmux-2.7 && ./configure --prefix=/opt/tmux-2.7 && make -j2 && make install
ARG PIERMUX_COMMIT=fbad099633383a8544dc34576dc4ae220188b3f2
RUN git clone https://github.com/kirinchen/piermux.git /src && cd /src && git checkout --detach "$PIERMUX_COMMIT"
COPY patches/ /extensions/patches/
RUN cd /src && git apply --check /extensions/patches/window-tabs.patch && git apply /extensions/patches/window-tabs.patch
COPY extensions/window-tabs.test.tsx /src/tests/window-tabs.test.tsx
COPY extensions/test-tmux-windows.sh /extensions/test-tmux-windows.sh
RUN bash /extensions/test-tmux-windows.sh && TMUX_TEST_BIN=/opt/tmux-2.7/bin/tmux bash /extensions/test-tmux-windows.sh
WORKDIR /src
RUN npm ci && npm run build && npm exec --yes --package=tsx@4.20.6 -- tsx --test tests/window-tabs.test.tsx && cargo test --release --manifest-path src-tauri/Cargo.toml windows::tests --locked && npm run tauri build -- --no-bundle -- --locked
RUN mkdir -p /out && cp src-tauri/target/release/piermux /out/ && cp LICENSE /out/LICENSE.piermux && cp /extensions/patches/window-tabs.patch /out/WINDOW_TABS.patch && git rev-parse HEAD > /out/UPSTREAM_COMMIT

FROM ubuntu:22.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends libwebkit2gtk-4.1-0 libssl3 librsvg2-2 libxdo3 libdbus-1-3 libsecret-1-0 gnome-keyring dbus-x11 ca-certificates fonts-noto-cjk locales xauth xvfb x11-utils && locale-gen en_US.UTF-8 && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/ /opt/piermux/
ENV LANG=en_US.UTF-8
RUN ldd /opt/piermux/piermux > /opt/piermux/ldd.txt && ! grep -q 'not found' /opt/piermux/ldd.txt
CMD ["/opt/piermux/piermux"]
