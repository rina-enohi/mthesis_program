# check.py - AZ/EL vs Power Plotting and Mapping Tool

JAXAおよび筑波大学のビームパターン測定に使用したプログラム。
ant30ログ・スペクトラムアナライザー出力（以降SPAログと略す）から以下の処理を行う。

- 指示値(AZ, EL)と実測値(AZ, EL)の差異を時系列プロット
- スペアナ出力の時間変化プロット
- SPAログに基づく(AZ, EL)マップ作成（単位: mW, dBm）

---

## 実行方法

```bash
python3 check.py ant30-log/ant30-raster_1-20240620142900.log spa-log/logspa-20240620_143106.txt --step_az 0.022 --step_el 0.04
```

### 引数の説明

| 引数            | 説明                                                         |
|------------------|--------------------------------------------------------------|
| `ant30filename`  | ant30ログファイルのパス（例: `ant30-log/ant30-*.log`）      |
| `spafilename`    | SPAログファイルのパス（例: `spa-log/logspa-*.txt`）         |
| `--step_az`      | AZ方向のビニングステップサイズ（単位: deg）|
| `--step_el`      | EL方向のビニングステップサイズ（単位: deg）|

---

## 出力ファイル

スクリプトの実行により、以下のPNG画像が自動生成される：

- `<ant30filename>_azel.png`  
  - コマンドと実測AZ/ELの比較プロット（単位: deg, arcsec）

- `<spafilename>_tod.png`  
  - AZ/EL位置に対するSPAパワーの時系列プロット

- `<spafilename>_map.png`  
  - 2Dヒートマップ（mWおよびdBmスケール）

---

## 処理フロー

1. **ログ読み込み**
   - `ant30-log` よりコマンド・実測AZ/ELを抽出
   - `spa-log` より受信パワーをdBm→mWへ変換し取得

2. **補間処理**
   - SPA時刻に対応するAZ/ELを補間により取得

3. **ビニング処理**
   - AZ/EL空間を2Dビンに分割し、受信パワーの平均値を計算

4. **マップ描画**
   - SPAパワーのmWスケール・dBmスケールの2Dヒートマップを作成

---

