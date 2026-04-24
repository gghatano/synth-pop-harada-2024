# Changelog

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
v0.x 中は破壊的変更を許容する。

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Phase 1 完了（2026-04-24）。合成人口生成の I/O・初期生成パイプラインと決定性担保が揃い、`synthpop-jp quickstart` コマンド 1 つで synthetic_households.csv と synthetic_persons.csv を生成できるようになった。これにより Phase 2（SA MVP）の土台が整った。

### Added
- Apache-2.0 LICENSE と NOTICE を追加
- CITATION.cff、CODE_OF_CONDUCT.md、CONTRIBUTING.md、DATASET.md を追加
- README.md（日本語 primary）と README.en.md（英語骨子）を追加
- Murata 2017 / Harada 2024 の位置付けを README 冒頭に明記
- Phase 1: 研究者が壊れた CSV を渡すと行番号付きで検証エラーが出る pydantic v2 ローダ ([#17](https://github.com/gghatano/synth-pop-harada-2024/pull/17), [Issue #12](https://github.com/gghatano/synth-pop-harada-2024/issues/12))
- Phase 1: SeedRegistry による階層 spawning と bitwise 一致の決定性 regression テスト ([#18](https://github.com/gghatano/synth-pop-harada-2024/pull/18), [Issue #16](https://github.com/gghatano/synth-pop-harada-2024/issues/16))
- Phase 1: SA 実装者が並列配列とドメインモデルを迷わず往復できる PopulationArrays + Registry + Household/Person ドメインモデル ([#19](https://github.com/gghatano/synth-pop-harada-2024/pull/19), [Issue #13](https://github.com/gghatano/synth-pop-harada-2024/issues/13))
- Phase 1: 9 family_type から統計に一致する初期人口をランダム生成する generate_initial_population ([#20](https://github.com/gghatano/synth-pop-harada-2024/pull/20), [Issue #14](https://github.com/gghatano/synth-pop-harada-2024/issues/14))
- Phase 1: `synthpop-jp quickstart` / `validate-config` CLI で 10 秒以内（実測約 1.1 秒）に synthetic_households.csv と synthetic_persons.csv を得られる ([#21](https://github.com/gghatano/synth-pop-harada-2024/pull/21), [Issue #15](https://github.com/gghatano/synth-pop-harada-2024/issues/15))

### Changed
- (なし)

### Deprecated
- (なし)

### Removed
- (なし)

### Fixed
- (なし)

### Security
- (なし)

---

## 過去バージョン

まだリリースされていません。初回リリース（v0.1.0 alpha、Phase 2 完了時点）時にこのセクションへ項目を追加します。
