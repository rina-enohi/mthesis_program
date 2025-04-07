# 連続波・電波ポインティング解析プログラムの使い方
クロススキャン観測から器差パラメータのフィッティングまでを行う一連のPythonスクリプトについて説明します。


## 解析に必要なファイル
- クロススキャン観測したときのant30ログ（ant30-obstable_name-YYYYMMDDHMS.log）
- パワーメーターログ (power-*.log)

※アンテナログ (azel-*.log)は不要


##  構成スクリプト一覧

| ファイル名             | 説明                                               |
|------------------------|----------------------------------------------------|
| 1. `scanplot.py`          | クロススキャン観測データの前処理・T_B 算出・閾値設定 |
| 2. `rp_peaksearch.py`     | 各スキャンプロファイルからピーク検出・中心オフセットを算出   |
| 3. `rp_instrument.py`     | 器差モデルの最小二乗フィッティングとプロット、パラメーター保存   |


※ rp_30cm.sh を実行すると1, 2のプログラムを連続して実行できる。

## 各プログラムの説明

---
## **1. rp_plot.py**

ant30ログとパワーメーターログを用いて、横軸：スキャンオフセット（AZ, EL）、縦軸：輝度温度 $T_{B}$ のプロットを
スキャンシーケンスごとに作成する。

プロット上の閾値線（赤線）をマウス操作で動かした後、
ウィンドウを閉じると、閾値線とスペクトル強度の交点の中点が計算され、天体の中心座標と実際に観測されたずれがoffset_C.txtに保存される。

### 実行例

```bash
python3 rp_plot.py ant30-2degrpsn-20240927161948.log power-2024092716.log
```

実行後、キャリブレーター温度 `T_amb`(単位 K)をキーボード入力する。

### 入力ファイル形式

#### 1. ant30ログファイル (ant30-obstable_name-YYYYMMDDHMS.log)
使用する観測テーブルはクロススキャン。
想定するスキャンのセットパターンは、" SetPattern      R,A,1,2 "
- R, OFF点が1回ずつ、ON点は十字なので2つ入れる。
- SetNumber（SetNumberを何回繰り返すか）はいくつでもよい。


#### 2. パワーメーターログファイル (power-YYYYMMDDHMS.log)

- タブ区切り形式：

```
[yyyy/mm/dd-hh:mm:ss.ms]    power_dBm
```
※日付時刻フォーマットは必要に応じて変更して下さい。

### プログラムの処理概要

1. **ログ読み込み**  
   - ant30ログ：AZ/EL座標、スキャンオフセット、観測時間を抽出  
   - パワーログ：dBm単位の受信電力と時刻を抽出

2. **ON/OFF/R 各観測時間の抽出と平均パワー計算**

3. **輝度温度 $T_{B}$ 計算**  
   $T_{B} = T_{amb} \cdot \frac{V_{ON} - V_{OFF}}{V_R - V_{OFF}}$
   

4. **AZ/ELスキャンごとに辞書を作成**

5. **プロットデータ出力**  
   各スキャンのデータを以下の形式でテキストファイル出力：

```
AZ [deg], EL [deg], offset [arcsec], power [dBm], T_B [K]
```

6. **インタラクティブなスキャンプロット表示**


### 出力ファイル構成
ant30-obstable_name-YYYYMMDDHMS_plotというディレクトリが作成され、その中にAZ, ELの各スキャンごとの
スキャンデータがテキスト形式で保存される。クロススキャン（SetNumber = 3）を3回行う場合、以下のようになる。

```
ant30-2degrpsn-20240927161948_plot/
├── az_scanplot_1.txt
├── el_scanplot_2.txt
├── az_scanplot_3.txt
├── el_scanplot_4.txt
├── az_scanplot_5.txt
├── el_scanplot_6.txt
└── threshold.tmp  ← 赤線の閾値を一時保存
```
- az_scanplot_1.txtはクロススキャン1回目のAZスキャン（横スキャン）のデータ
- el_scanplot_1.txtはクロススキャン1回目のELスキャン（縦スキャン）のデータ

### インタラクティブ操作の説明

- 赤線をクリックして選択して移動
- 再クリックで線の選択解除ができる
- 各プロットの閾値は `threshold.tmp` に自動保存される（rp_peaksearch.pyで読み込み後に自動で消去される）


### プロットの構成

- 左列：AZスキャン  
- 右列：ELスキャン  
- 横軸：スキャンオフセット [arcsec]  
- 縦軸：$T_{B}$ [K]  
- 赤線：$T_{B}$ の閾値（ドラッグ可能）


---

## **2. rp_peaksearch.py**

ディレクトリ "ant30-obstable_name-YYYYMMDDHMS_plot" に保存された `az_scanplot_*.txt` および `el_scanplot_*.txt` を用いて、
**AZ/ELスキャンにおける輝度温度$T_{B}$のピーク中心位置**を抽出・プロットし、**器差モデルフィッティングに必要な位置・オフセット情報**をテキスト出力する。

###  実行方法

```bash
python3 rp_peaksearch.py ディレクトリ名
```

### 実行例

```bash
python3 rp_peaksearch.py ant30-2degrpsn-202410071532_plot
```

### 入力ファイル構成

対象ディレクトリ（例：`ant30-2degrpsn-202410071532_plot/`）には、以下のようなファイルが含まれる必要がある：

- `az_scanplot_1.txt`, `el_scanplot_2.txt`, ...  
  - 輝度温度$T_{B}$計算済みのスキャンデータ（Setごとに2ファイル）

- `threshold.tmp`  
  - 各プロットに対する閾値（赤線の高さ）が事前に保存されている一時ファイル（例：`scanplot.py` による作成）


### プログラム処理概要

1. **ディレクトリ内ファイルの読み込み**
   - 各スキャンファイル（AZ, EL）を辞書に読み込み、SetNumber に従ってペア化

2. **threshold.tmp の読み込み**
   - 各スキャンの閾値を読み込み、赤線の高さとして使用

3. **プロット処理**
   - 各AZスキャン / ELスキャンの輝度温度$T_{B}$をプロット
   - 閾値とデータの交点を線形補間で検出
   - 交点間の中央（ピーク）位置に青線を描画
   - タイトル・凡例を含む2列表示のサブプロットを生成
   - プロットを `threshold.png` として保存

4. **ピーク位置とオフセットの記録**
   - スキャンオフセットの中心（交点間の平均）を dAZ, dEL として計算
   - 対応する実測AZ, EL位置を線形補間で取得
   - 結果を `offset_C.txt` に出力


### 出力ファイル

### `threshold.png`

- 各SetのAZスキャン・ELスキャンを2列に並べた$T_{B}$プロット
- 赤線：指定された閾値
- 緑点線：交点
- 青線：交点中心（ピーク位置）

### `offset_C.txt`

- 器差補正に必要なデータをまとめたテキストファイル（単位：deg）

```
AZ1      EL1      dAZ     AZ2      EL2      dEL
------   ------   ------  ------   ------   ------
XXX.XXX  XX.XXX   0.0001  XXX.XXX  XX.XXX   0.0002
```

- `AZ1`, `EL1`：AZスキャン時の中心位置（deg）
- `dAZ`：AZ方向のオフセット（deg）
- `AZ2`, `EL2`：ELスキャン時の中心位置（deg）
- `dEL`：EL方向のオフセット（deg）


###  注意

- `threshold.tmp` が存在しないと実行できない（`rp_plot.py` を先に実行しておく必要がある）
- スキャン数（SetNumber）は `_scanplot_*.txt` ファイルのペア数から自動判定される
- 単位：スキャンオフセットは [arcsec]、出力は [deg] に変換される
- `offset_L.txt`は輝線ポインティングから求まるデータセット (AZ, EL, dAZ, dEL)。
   AZとELそれぞれのピークの中心からのずれ（dAZ, dEL）は分光計PCにあるプログラム QLOOK.pyが算出する。これをもとに自分で作成する。（`分光計使用マニュアル_20240808.pdf`を参照）


---

## **3. rp_instrument.py**

rp_peaksearch.pyで出力された連続波（Continuum）および輝線（Line）ポインティングデータを用いて、
選択した器差モデルに適合する器差パラメーターを最小二乗フィッティングにより求めるプログラム。

### 実行方法

```bash
python3 rp_instrument.py
```

### 使用手順：
1. `offset_data/` フォルダ内に以下のファイルを準備：
    - `offset_C.txt`：連続波ポインティング結果
    - `offset_L.txt`：輝線ポインティング結果

2. 実行すると以下の器差モデルを選択できる：
    - [1]: 60 cm telescope model（Nakajima 2007）
    - [2]: 60 cm model 改良版
    - [3]: Optical pointing model（Koyama thesis）

3. 初期パラメータは手入力または `ant30_phaseC0.conf` から自動読み込み。

※中央制御PCで実行する場合、`ant30_phaseC0.conf`のパスを書き換えてください。

各データの形式：
-------------------------------
【輝線ポインティング（offset_L.txt）】
    AZ, EL, dAZ, dEL

【連続波ポインティング（offset_C.txt）】
    AZ_1, EL_1, dAZ（AZスキャン）
    AZ_2, EL_2, dEL（ELスキャン）

### 処理内容：

- `dAZ`, `dEL` の観測値とモデルによる推定値との差（残差）を最小化し、共通の器差パラメーターを決定。
- 残差（RMS）を before / after で比較。
- 最適化された器差パラメーターを `ant30_phaseC0.conf` ファイルに追記。
- プロット結果を保存（png出力）。

### 出力：

- `result1_*.png`：dAZ vs dEL の円プロット（before/after）
- `result2_*_L.png`：輝線ポインティングの詳細プロット（offset_L.txtのみの場合）
- `result2_*_C.png`：連続波ポインティングの詳細プロット（offset_C.txtのみの場合）
- `result2_*_L_and_C.png`：両方の合成プロット（offset_L.txt, offset_C.txtの両方ある場合）


---

# 全体ワークフロー

```text
ant30ログ, powerログ
      │
      ▼
[rp_plot.py]
      ├─> T_B vs offset プロット作成 (閾値を設定)
      └─> *_scanplot_*.txt + threshold.tmp
               │
               ▼
       [rp_peaksearch.py]
               ├─> 閾値でピーク抽出
               └─> offset_C.txt 生成
                      │
                      ▼
         [rp_instrument.py]
               ├─> モデル選択＆フィッティング
               ├─> RMS・フィット評価
               └─> ant30_phaseC0.conf に保存
```

---

