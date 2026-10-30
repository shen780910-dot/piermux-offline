import * as React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WindowTabs } from "../src/desktop/WindowTabs";
import { emptyLocalHostForm } from "../src/lib/types";

test("new desktop connections require no SSH credentials", () => {
  const form = emptyLocalHostForm();
  assert.equal(form.auth_type, "local");
  assert.equal(form.ssh_host, "");
  assert.equal(form.ssh_user, "");
  assert.equal(form.private_key_path, null);
  assert.equal(form.password, null);
});

const session = { socket: "default", name: "project-a", attached: true, activity: "", windows: 2 };
function render(windows: unknown[], enabled = true, sessionName = "project-a") {
  const client = new QueryClient();
  client.setQueryData(["tmux-windows", "host-1", "default", sessionName], windows);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <WindowTabs hostId="host-1" session={{ ...session, name: sessionName }} enabled={enabled} onSelected={() => {}} />
    </QueryClientProvider>,
  );
}

test("renders nonzero indexes, Unicode names and the active window", () => {
  const html = render([
    { id: "@2", index: 4, name: "agent-1", active: false },
    { id: "@9", index: 8, name: "專案 A | review", active: true },
  ]);
  assert.match(html, /aria-pressed="false"/);
  assert.match(html, /aria-pressed="true"/);
  assert.match(html, /專案 A \| review/);
  assert.match(html, />8<\/span>/);
});

test("empty windows offers an explicit state", () => {
  assert.match(render([]), /沒有可用的 window/);
});

test("disconnected sessions do not show actionable cached windows", () => {
  const html = render([{ id: "@2", index: 0, name: "old-agent", active: true }], false);
  assert.match(html, /連線後載入分頁/);
  assert.doesNotMatch(html, /old-agent/);
});

test("project caches stay separate", () => {
  const client = new QueryClient();
  client.setQueryData(["tmux-windows", "host-1", "default", "project-a"], [{ id: "@1", index: 0, name: "A-only", active: true }]);
  client.setQueryData(["tmux-windows", "host-1", "default", "project-b"], [{ id: "@2", index: 0, name: "B-only", active: true }]);
  const html = renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <WindowTabs hostId="host-1" session={{ ...session, name: "project-b" }} enabled={true} onSelected={() => {}} />
    </QueryClientProvider>,
  );
  assert.match(html, /B-only/);
  assert.doesNotMatch(html, /A-only/);
});
