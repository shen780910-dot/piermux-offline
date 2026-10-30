# 獨立程式碼檢查

Important 已修正：所有 tmux window 查詢／切換改用精確 session target，避免名稱模糊比對誤切其他專案；已加入 Rust 測試。

無其他 Critical 或 Important 阻擋項目。

Minor 留待目標機驗收：目前 React 測試涵蓋輸出、斷線、空清單與專案快取隔離，尚未自動化實際點擊 invoke、pending／失敗重試與舊 mutation 完成的互動測試。

程式碼檢查已確認 keyed mount、query key、aliveRef 的防護；編譯與測試結果以 Actions 為準，tmux 2.7 真機與 SSH 仍需驗收。
