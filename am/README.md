# am-11.0 (https://lweb.cfa.harvard.edu/~spaine/am/) の解析プログラム

## amc_file

各大気圧ごとの大気温度、水、オゾン混合比が記載されたシミュレーション計算に必要な設定ファイル。

## netCDF_file

NASA Global Modeling and Assimilation Office, (https://gmao.gsfc.nasa.gov/reanalysis/merra-2/)
から取得したデータ。amc_fileの作成の元データ。

## output_file

シミュレーション結果の出力データ。全て天頂角Z=45として計算した結果です。

ファイル名のフォーマット：
DomeFuji_season_percentile.out
