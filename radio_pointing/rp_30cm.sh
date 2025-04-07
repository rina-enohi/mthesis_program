#!/bin/sh

# 実行方法
# ./rp_30cm.sh ant30.log power.log

# ターミナルからログファイル名を引数として受け取る
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <ant30log> <powerlog>"
    exit 1
fi

ANT30LOG=$1
POWERLOG=$2

# rp_plot.py を実行
echo "Running rp_plot.py with $ANT30LOG and $POWERLOG"
python3 rp_plot.py $ANT30LOG $POWERLOG

# rp_plot.pyの終了コードを確認
if [ "$?" -ne 0 ]; then
    echo "Error: rp_plot.py failed. Exiting."
    exit 1
fi

# rp_plot.pyで生成されたantt30log +"_plot" のフォルダを取得
SCAN_FOLDER="${ANT30LOG%.log}_plot" 

if [ ! -d "$SCAN_FOLDER" ]; then
    echo "Error: Folder $SCAN_FOLDER not found. Exiting."
    exit 1
else
    echo "Found folder: $SCAN_FOLDER"
fi

# rp_peaksearch.py を実行 (rp_plot.py で生成されたフォルダを引数に使用)
echo "Running rp_peaksearch.py with $SCAN_FOLDER"
python3 rp_peaksearch.py $SCAN_FOLDER

# rp_peaksearch.py の終了コードを確認
if [ "$?" -ne 0 ]; then
    echo "Error: rp_peaksearch.py failed. Exiting."
    exit 1
fi

echo "All scripts executed successfully!"

