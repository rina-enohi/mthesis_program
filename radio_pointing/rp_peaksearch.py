#!python3

import numpy as np
import pandas as pd
import glob
import os
from scipy import interpolate
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable


"""
実行例　python3 rp_peaksearch.py 解析したいファイルが入ったディレクトリ名

入力ファイル(ant30-2degrpsn-202410071532_plot_*.txt)を用いて
指定した閾値と求めたピーク中心位置をプロット

器差モデルフィットに必要な情報（AZ, EL, dAZ, dEL）
出力ファイル(ant30-2degrpsn-202410071532_offset.txt) を作成
"""

def main(directory):
    """
    キーボード入力したSetNumberをもとに、各AZ, ELスキャンの閾値をキーボード入力で設定。
    閾値の線と、エッジの範囲を網掛けした図を表示する
    器差パラ計算に必要な情報をテキストファイルに保存
    """
    # 入力したディレクトリ内にある _scanplot_*.txt ファイルの総数を2で割った値をSetNumberに格納
    plot_files = glob.glob(os.path.join(directory, '*_scanplot_*.txt'))
    SetNumber = len(plot_files) // 2
    plot_and_write(directory, SetNumber)


def read_inputfile(directory, SetNumber):
    """
    指定されたディレクトリの中にあるファイルを1つずつ読み込み、ファイル名に応じてデータを読み込む。
    SetNumberに応じて、AZ/ELデータの列名を自動設定。
    読み込みファイルのフォーマットが変わったので変更
    """
    files = glob.glob(os.path.join(directory, '*_scanplot_*.txt'))
    
    ret = {}

    for count in range(1, SetNumber + 1):
        az_idx = 2 * count - 1 
        el_idx = 2 * count      
        
        for file_path in files:
            file_name = os.path.basename(file_path)

            if f"az_scanplot_{az_idx}.txt" in file_name:
                data = pd.read_csv(file_path, header=None, skiprows=1, names=["AZ","EL","AZ_scanoffset", "power", "T_B"])
                ret[f"AZ_{count}"] = data  # 辞書に保存

            elif f"el_scanplot_{el_idx}.txt" in file_name:
                data = pd.read_csv(file_path, header=None, skiprows=1, names=["AZ","EL","EL_scanoffset", "power", "T_B"])
                ret[f"EL_{count}"] = data  # 辞書に保存

    return ret

mpl.rcParams.update({'font.size': 10})
mpl.rcParams.update({'axes.grid': True})
mpl.rcParams.update({'grid.linestyle': ':'})

temp_file = "threshold.tmp"

def load_thresholds_from_temp(temp_file, SetNumber):
    """一時ファイルから閾値を読み込みリストに格納"""
    thresholds_AZ = []
    thresholds_EL = []

    if os.path.exists(temp_file):
        with open(temp_file, "r") as f:
            lines = f.readlines()
            # AZ と EL に分割して読み込み
            for i in range(SetNumber):
                thresholds_AZ.append(float(lines[2 * i].strip()))
                thresholds_EL.append(float(lines[2 * i + 1].strip()))
        os.remove(temp_file)  # 読み込み後に削除
        print(f"Loaded thresholds from temp file: {temp_file}")
    else:
        raise FileNotFoundError(f"Temp file {temp_file} not found.")

    return thresholds_AZ, thresholds_EL

def plot_and_write(directory, SetNumber):
    """
    read_inputfile()で作成した辞書を使って、AZとELのスキャンをプロット。
    閾値とエッジ部分を表示し、確認のためのプロットを行う。タイトルには閾値とオフセットを入れる。
    出力ファイル(offset_c.txt) 単位は全て[deg]
    AZ_1, EL_1, dAZ, AZ_2, EL_2, dEL を作成。
    """
    ret = read_inputfile(directory, SetNumber) 
    fig, ax = plt.subplots(SetNumber, 2, figsize=(3 * SetNumber, 3 * SetNumber)) 

    # AZとELの閾値を保持するリスト
    thresholds_AZ, thresholds_EL = load_thresholds_from_temp(temp_file, SetNumber)

    # 輝線データ用
    #az_at_center_list = [] # AZ
    #el_at_center_list = [] # EL 
    #x_center_list = [] # dAZ
    #xx_center_list = [] # dEL

    # 連続波データ用
    # AZ scan
    az_at_center_list = [] # AZ1
    el_at_center_list = [] # EL1 
    x_center_list = []     # dAZ

    # EL scan
    az_at_center_list2 = [] # AZ2
    el_at_center_list2 = [] # EL2
    xx_center_list = []     # dEL    

    for count in range(1, SetNumber + 1):
        threshold_AZ = thresholds_AZ[count - 1]
        threshold_EL = thresholds_EL[count - 1]

        ###################################################################### AZデータ処理
        x = np.array(ret[f"AZ_{count}"]["AZ_scanoffset"])
        y = np.array(ret[f"AZ_{count}"]["T_B"])
        az_real_1 = np.array(ret[f"AZ_{count}"]["AZ"])
        el_real_1 = np.array(ret[f"AZ_{count}"]["EL"])   
        
        ax[count - 1, 0].scatter(x, y, label="data",s=10)
        ax[count - 1, 0].axhline(y=threshold_AZ, color='r', linestyle='-', label=f'threshold = {threshold_AZ}')
        ax[count - 1, 0].set_xlabel("AZ Scan Offset [arcsec]")
        ax[count - 1, 0].set_ylabel(r"$T_B$ [K]")
        ax[count - 1, 0].set_title(f"AZ_scan, Set {count}")
        
        # 交点の計算と描画
        index = np.where(np.diff(np.sign(y - threshold_AZ)))[0]
        x_intersections = []

        # 線形補間で交点を計算
        for idx in index:
            x1, x2 = x[idx], x[idx + 1]
            y1, y2 = y[idx], y[idx + 1]
            slope = (y2 - y1) / (x2 - x1)
            intercept = y1 - slope * x1
            cross_x = (threshold_AZ - intercept) / slope
            x_intersections.append(cross_x)
        
        # 垂直な点線を閾値とプロットの交点に描画
        for cross_x in x_intersections:
            ax[count - 1, 0].axvline(x=cross_x, color='g', linestyle='--', label=f'x = {cross_x:.2f}')
        
        # 両端の交点の中心に青線を描画（点線の中心）
        if len(x_intersections) >= 2:
            x_center = np.mean(x_intersections)
            ax[count - 1, 0].axvline(x=x_center, color='b', linestyle='-', label=f'Center x = {x_center:.2f}') 

            # 線形補間で az_scanoffset = 0 のときの AZ, EL の値を取得
            f_az_1 = interpolate.interp1d(x, az_real_1, kind='linear', fill_value="extrapolate")
            f_el_1 = interpolate.interp1d(x, el_real_1, kind='linear', fill_value="extrapolate")
            az_at_zero = f_az_1(0)  
            el_at_zero = f_el_1(0)              

            # リストに追加
            az_at_center_list.append(az_at_zero) # AZ1
            el_at_center_list.append(el_at_zero) # EL1
            x_center_list.append(x_center)       # dAZ

        ax[count - 1, 0].legend()

        #################################################################### ELデータ処理
        xx = np.array(ret[f"EL_{count}"]["EL_scanoffset"])
        yy = np.array(ret[f"EL_{count}"]["T_B"])
        az_real_2 = np.array(ret[f"EL_{count}"]["AZ"])
        el_real_2 = np.array(ret[f"EL_{count}"]["EL"])  
        
        ax[count - 1, 1].scatter(xx, yy, label="data",s=10)
        ax[count - 1, 1].axhline(y=threshold_EL, color='r', linestyle='-', label=f'threshold = {threshold_EL}')
        ax[count - 1, 1].set_xlabel("EL Scan Offset [arcsec]")
        ax[count - 1, 1].set_ylabel(r"$T_B$ [K]")
        ax[count - 1, 1].set_title(f"EL_scan, Set {count}")
        
        # 交点の計算とプロット
        index = np.where(np.diff(np.sign(yy - threshold_EL)))[0]
        xx_intersections = []

        for idx in index:
            x1, x2 = xx[idx], xx[idx + 1]
            y1, y2 = yy[idx], yy[idx + 1]
            slope = (y2 - y1) / (x2 - x1)
            intercept = y1 - slope * x1
            cross_xx = (threshold_EL - intercept) / slope
            xx_intersections.append(cross_xx)
        
        for cross_xx in xx_intersections:
            ax[count - 1, 1].axvline(x=cross_xx, color='g', linestyle='--', label=f'x = {cross_xx:.2f}')
        
        if len(xx_intersections) >= 2:
            xx_center = np.mean(xx_intersections)
            ax[count - 1, 1].axvline(x=xx_center, color='b', linestyle='-', label=f'Center x = {xx_center:.2f}') 

            # 線形補間で el_scanoffset = 0 のときの AZ, EL の値を取得
            f_az_2 = interpolate.interp1d(xx, az_real_2, kind='linear', fill_value="extrapolate")
            f_el_2 = interpolate.interp1d(xx, el_real_2, kind='linear', fill_value="extrapolate")
            az_at_zero_2 = f_az_2(0)
            el_at_zero_2 = f_el_2(0)   

            # リストに追加
            el_at_center_list2.append(el_at_zero_2) # EL2
            az_at_center_list2.append(az_at_zero_2) # AZ2
            xx_center_list.append(xx_center)      # dEL

        ax[count - 1, 1].legend()

    fig.tight_layout()
    #plt.savefig(os.path.join(directory, directory + "_threshold.png"))
    plt.savefig(os.path.join(directory, "threshold.png"))
    plt.show()

    # 結果をテキストファイルに保存
    # 輝線データ用フォーマット
    #outputfile = os.path.join(directory, "offset.txt")
    #with open(outputfile, 'w') as f:
    #    f.write("AZ[deg], EL[deg], dAZ[deg], dEL[deg]\n")
    #    for az_at_center, x_center, el_at_center, xx_center in zip(az_at_center_list, x_center_list, el_at_center_list, xx_center_list):
    #        f.write(f"{az_at_center:.6f},{el_at_center:.6f},{x_center/3600:.6f},{xx_center/3600:.6f}\n")

    # 連続波データ用フォーマット（クロススキャンで得られるデータセットはこっち）
    outputfile = os.path.join(directory, "offset_C.txt")
    with open(outputfile, 'w') as f:
        f.write("AZ1, EL1, dAZ, AZ2, EL2, dEL\n")
        for az_at_center, el_at_center, x_center, az_at_center2, el_at_center2, xx_center in zip(az_at_center_list, el_at_center_list, x_center_list, az_at_center_list2, el_at_center_list2, xx_center_list):
            f.write(f"{az_at_center:.6f}\t{el_at_center:.6f}\t{x_center/3600:.6f}\t{az_at_center2:.6f}\t{el_at_center2:.6f}\t{xx_center/3600:.6f}\n")# x_center [arcsec] → [deg]

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', help='Enter directories you want to analyze')
    
    args = parser.parse_args()
    main(args.directory)
