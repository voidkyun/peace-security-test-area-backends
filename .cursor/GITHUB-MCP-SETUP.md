# Cursor + GitHub MCP セットアップ手順

## 1. GitHub PAT を取得する

1. [GitHub: Personal access tokens (classic)](https://github.com/settings/tokens/new) を開く。
2. **Note**: 例）`Cursor MCP`
3. **Expiration**: 任意（90日または No expiration）
4. **Scopes**: **repo** にチェック（リポジトリの読み書き）
5. **Generate token** で作成し、表示されたトークンをコピー（一度しか表示されません）。

## 2. MCP 設定に PAT を設定する

- プロジェクトで使う場合  
  - ファイル `.cursor/mcp.json` を開く（存在しない場合は `.cursor/mcp.json.example` をコピーして `mcp.json` として保存）。
  - `YOUR_GITHUB_PAT` を、コピーした PAT に置き換えて保存。
- 全プロジェクトで使う場合（推奨）  
  - `%USERPROFILE%\.cursor\mcp.json` に上記と同じ `mcpServers.github` の設定を追加し、`YOUR_GITHUB_PAT` を実際の PAT に置き換える。

**注意**: `mcp.json` は `.gitignore` 済みです。PAT を書いたファイルをコミットしないでください。

### Docker でローカルサーバーを使う場合

Remote Server（URL）が使えない環境では、`.cursor/mcp.json` を次のようにします。

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_GITHUB_PAT"
      }
    }
  }
}
```

## 3. Cursor を再起動する

- 設定変更後は **Cursor を完全に終了してから起動し直す**と確実です。

## 4. 動作確認

- **Settings → Tools & Integrations → MCP** で GitHub が有効（緑）になっているか確認。
- Agent で「このリポジトリの open な Issue 一覧を出して」と依頼し、一覧が取得できるか確認。

## 参考

- [GitHub MCP Server](https://github.com/github/github-mcp-server)
- [Cursor MCP ドキュメント](https://cursor.com/docs/context/mcp/install-links)
