# tmux window 分頁擴充

使用者已要求直接擴充現有 Piermux。沿用原本的配色、字型與操作區，不改遠端 agent 提交方式。

1. 在 session 的 attach 畫面、終端機上方加入可點選的 window 按鈕列；session 對應專案，window 可自行命名為 agent 名稱。
2. Rust 透過現有 SSH 連線列出 window，並以穩定 window ID 切換；不執行 agent 提交、刪除或重啟。
3. 處理載入、錯誤重試、空清單、切換中的停用狀態與長名稱水平捲動，每 10 秒同步 tmux 快捷鍵造成的切換。
4. 以 Rust 單元測試檢查格式解析與不合法 window ID；TypeScript 編譯、Xvfb 視窗測試與離線封裝沿用 Actions。
5. 以固定上游 commit 的 patch 交付，保留 MIT LICENSE；目標機驗收仍包含 tmux 2.7、X11、SSH。

切換 window 會切換該 session 的作用中 window，其他連到同一 session 的 client 也可能同步切換。
分頁數不代表排程工作數；本次不自動偵測或保證 5 個 agent 名額。
