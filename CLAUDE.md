# CLAUDE.md

# CLAUDE.md (プロジェクトメモリ)

## 概要
開発を進めるうえで遵守すべき標準ルールを定義します。

## プロジェクト構造
### ドキュメントの分類
本リポジトリは、1つのアプリケーション開発専用のリポジトリです（現在の対象アプリケーションは `docs/product-requirements.md` で定義します）。システム開発において、対象業務の関係者間で単語・用語の認識ずれを防ぐため、業務に関する言葉と意味を定義して共通言語として共有する「ユビキタス言語」がドメイン駆動設計のプラクティスとして普及しています。

#### 1. 永続的ドキュメント (`docs/`)
アプリケーション全体の「何を学ぶか」「どう作るか」を定義する恒久的なドキュメントであり、基本設計や方針が変わらない限り更新されません。

* product-requirements.md - プロダクト要求定義書
  * プロダクトビジョンと目的
  * ターゲットユーザーと課題・ニーズ
  * 主要な機能一覧
  * 成功の定義
  * ビジネス要件
  * ユーザーストーリー
  * 受け入れ条件
  * 機能要件
  * 非機能要件
* functional-design.md - 機能設計書
  * 機能ごとのアーキテクチャ
  * システム構成図
  * データモデル定義 (ER図含む)
  * コンポーネント設計
  * ユースケース図、画面遷移図、ワイヤフレーム
  * API設計 (将来的にバックエンドと連携する場合)
* architecture.md - 技術仕様書
  * テクノロジースタック
  * 開発ツールと手法
  * 技術的制約と要件
  * パフォーマンス要件
* repository-structure.md - リポジトリ構造定義書
  * フォルダ・ファイル構成
  * ディレクトリの役割
  * ファイル配置ルール
* development-guidelines.md - 開発ガイドライン
  * コーディング規約 (命名規則、スタイリング規約、テスト規約、Git規約)
* glossary.md - ユビキタス言語定義
  * ドメイン用語の定義
  * ビジネス用語の定義
  * UI/UX用語の定義
  * 英語・日本語対応表
  * コード上の命名規則

#### 2. 作業単位のドキュメント (`.steering/[YYYYMMDD]-[開発タイトル]/`)
特定の開発作業における「今回何をするか」を定義する一時的なステアリングファイルです。作業完了後は参照用として保持されますが、新しい作業では新しいディレクトリを作成します。

* requirements.md - 今回の作業の要求内容
  * 変更・追加する機能の説明
  * ユーザーストーリー
  * 受け入れ条件
  * 制約事項
* design.md - 変更内容の設計
  * 実装アプローチ
  * 変更するコンポーネント
  * データ構造の変更
  * 影響範囲の分析
* tasklist.md - タスクリスト
  * 具体的な実装タスク
  * タスクの進捗状況
  * 完了条件

### ステアリングディレクトリの命名規則
.steering/[YYYYMMDD]-[開発タイトル]/

例:
* .steering/20250103-initial-implementation/
* .steering/20250115-add-tag-feature/
* .steering/20250120-fix-filter-bug/
* .steering/20250201-improve-performance/

---

## 開発プロセス

### 初回セットアップ時の手順
1. フォルダ作成
   mkdir -p docs
   mkdir -p steering
2. 永続的ドキュメント作成 (`docs/`)
   アプリケーション全体の設計を定義します。各ドキュメント作成後、必ず確認・承認を得てから次に進みます。
   * docs/product-requirements.md - プロダクト要求定義書
   * docs/functional-design.md - 機能設計書
   * docs/architecture.md - 技術仕様書
   * docs/repository-structure.md - リポジトリ構造定義書
   * docs/development-guidelines.md - 開発ガイドライン
   * docs/glossary.md - ユビキタス言語定義
   * 重要: 1ファイルごとに作成後、必ず確認・承認を得てから次のファイル作成を行う
3. 初回実装用のステアリングファイル作成
   初回実装用のディレクトリを作成し、実装に必要なドキュメントを配置します。
   mkdir -p steering/[YYYYMMDD]-initial-implementation
   作成するドキュメント:
   * .steering/[YYYYMMDD]-initial-implementation/requirements.md - 初回実装の要求
   * .steering/[YYYYMMDD]-initial-implementation/design.md - 実装設計
   * .steering/[YYYYMMDD]-initial-implementation/tasklist.md - 実装タスク
4. 環境セットアップ
5. 実装開始
   .steering/[YYYYMMDD]-initial-implementation/tasklist.md に基づいて実装を進めます。
6. 品質チェック

### 機能追加・修正時の手順
1. 影響分析
   * 永続的ドキュメント (`docs/`) への影響を確認
   * 変更が基本設計に影響する場合は docs/ を更新
2. ステアリングディレクトリ作成
   新しい作業用のディレクトリを作成します。
   mkdir -p .steering/[YYYYMMDD]-[開発タイトル]
   例:
   mkdir -p .steering/20250115-add-tag-feature
3. 作業ドキュメント作成
   作業単位のドキュメントを作成します。各ドキュメント作成後、必ず確認・承認を得てから次に進みます。
   * .steering/[YYYYMMDD]-[開発タイトル]/requirements.md
   * .steering/[YYYYMMDD]-[開発タイトル]/design.md - 設計
   * .steering/[YYYYMMDD]-[開発タイトル]/tasklist.md - タスクリスト
   * 重要: 1ファイルごとに作成後、必ず確認・承認を得てから次のファイル作成を行う
4. 永続的ドキュメント更新（必要な場合のみ）
   変更が基本設計に影響する場合、該当する docs/ 内のドキュメントを更新します。
5. 実装開始
   .steering/[YYYYMMDD]-[開発タイトル]/tasklist.md に基づいて実装を進めます。
6. 品質チェック

---

## ドキュメント管理の原則

### 永続的ドキュメント (`docs/`)
* アプリケーションの基本設計を記述
* 頻繁に更新されない
* 大きな設計変更時のみ更新
* プロジェクト全体の「北極星」として機能

### 作業単位のドキュメント (`.steering/`)
* 特定の作業・変更に特化
* 作業ごとに新しいディレクトリを作成
* 作業完了後は履歴として保持
* 変更の意図と経緯を記録

---

## 図表・ダイアグラムの記載ルール

### 記載場所
設計図やダイアグラムは、関連する永続的ドキュメント内に直接記載します。独立した diagrams フォルダは作成せず、手間を最小限に抑えます。

* ER図、データモデル図 → functional-design.md 内に記載
* ユースケース図 → functional-design.md または product-requirements.md 内に記載
* 画面遷移図、ワイヤフレーム → functional-design.md 内に記載
* システム構成図 → functional-design.md または architecture.md 内に記載

### 記述形式
1. Mermaid記法（推奨）
   * Markdownに直接埋め込める
   * バージョン管理が容易
   * ツール不要で編集可能
   ```mermaid
   graph TD
   A[ユーザー] --> B[タスク作成]
   B --> C[タスク一覧]
   C --> D[タスク編集]
   C --> E[タスク削除]