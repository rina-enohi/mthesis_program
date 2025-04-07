#!python3

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
import sys
import re
import os
from datetime import datetime
import matplotlib as mpl
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt

mpl.rcParams.update({'font.size': 12})
mpl.rcParams.update({'axes.grid': True})
mpl.rcParams.update({'grid.linestyle': ':'})

"""
実行方法：python3 rp_instrument.py 

rp_peaksearch.pyの出力結果 offset_C.txtと、輝線ポインティングで得られたoffset_L.txt をoffset_dataのフォルダに入れる。

beforeはフィッティング前の結果、afterはフィッティング前後の残差(フィッティングによりどうよくなったか)を表す。

輝線データのフォーマット：AZ, EL, dAZ, dEL
連続波データのフォーマット：AZ1, EL1, dAZ, AZ2, EL2, dEL
輝線と連続波それぞれの残差の二乗和を足し合わせたものを最小化して、dAZ, dEL共通の器差パラメーターを求める。

"""

#ant30conf = r"/home/user/control/tcs01/etc/ant30_phaesC0.conf" # ant30op
ant30conf = "ant30_phaseC0.conf"
folder = "offset_data" # 解析するファイルのあるフォルダ名


def main():
    title = """\
    ********************************
    ant30 radio pointing --analysis--
        2024/11/18  R.Enohi
    ********************************

    解析するファイルを /offset_data 内に入れてください。
    フィッティングに使用する器差モデル式を選択してください
    [1]:60 cm model 
    [2]:60 cm model 改良版
    [3]:Optical pointing model
    """
    print(title)

    # モデル選択
    while True:
        select = input("選択>>")
        
        if select == "1":
            print("60 cm telescope model でフィッティングします")
            model_name = '60cm_model'
            initial_guess = []

            while True:
                proceed = input("\nフィッティングの初期パラメーターに器差ファイル(ant30_phaseC0.conf)の値を使用しますか？：[y]es / [n]o: ").strip().lower()
                
                if proceed == "y":
                    initial_guess = read_old_kisapara_from_conf(model_name)
                    print("ant30_phaseC0.confの器差パラメータを使用します。\n", initial_guess)
                    break  
                
                elif proceed == "n":
                    print("初期パラメータを入力して下さい。\n")
                    try:
                        initial_guess = []
                        for i in range(6): # B0 - B5 まで6個
                            value = float(input(f"B{i} = "))
                            initial_guess.append(value)
                        print("入力したパラメータ\n", initial_guess)
                        proceed2 = input("\nこのパラメーターを使用しますか？：[y]es / [n]o: ").strip().lower()
                        
                        if proceed2 == "y":
                            break  
                    
                    except ValueError:
                        print("無効な入力です。数値を入力してください。")

            popt = run_fit(model_name, initial_guess)
            if popt is not None:
                write_in_conf(ant30conf, popt, model_name)
            break
        
        elif select == "2":
            print("60 cm model 改良版でフィッティングします")
            model_name = '60cm_model_2'
            initial_guess = []

            while True:  
                proceed = input("\nフィッティングの初期パラメーターに器差ファイル(ant30_phaseC0.conf)の値を使用しますか？：[y]es / [n]o: ").strip().lower()
                
                if proceed == "y":
                    initial_guess = read_old_kisapara_from_conf(model_name)
                    print("ant30_phaseC0.confの器差パラメータを使用します。\n", initial_guess)
                    break  
                
                elif proceed == "n":
                    print("初期パラメータを入力して下さい。\n")
                    try:
                        initial_guess = []
                        for i in range(10): # B0 - B9 まで10個
                            value = float(input(f"B{i} = "))
                            initial_guess.append(value)
                        print("入力したパラメータ\n", initial_guess)
                        proceed2 = input("\nこのパラメーターを使用しますか？：[y]es / [n]o: ").strip().lower()
                        
                        if proceed2 == "y":
                            break  
                    
                    except ValueError:
                        print("無効な入力です。数値を入力してください。")

            popt = run_fit(model_name, initial_guess)
            if popt is not None:
                write_in_conf(ant30conf, popt, model_name)
            break

        elif select == "3":
            print("Optical pointing model でフィッティングします")
            model_name = 'optical_model'
            initial_guess = []

            while True:  
                proceed = input("\nフィッティングの初期パラメーターに器差ファイル(ant30_phaseC0.conf)の値を使用しますか？：[y]es / [n]o: ").strip().lower()
                
                if proceed == "y":
                    initial_guess = read_old_kisapara_from_conf(model_name)
                    print("ant30_phaseC0.confの器差パラメータを使用します。\n", initial_guess)
                    break  
                
                elif proceed == "n":
                    print("初期パラメータを入力して下さい。\n")
                    try:
                        initial_guess = []
                        for i in range(1, 16): # A1 - A15 まで15個
                            value = float(input(f"A{i} = "))
                            initial_guess.append(value)
                        print("入力したパラメータ\n", initial_guess)
                        proceed2 = input("\nこのパラメーターを使用しますか？：[y]es / [n]o: ").strip().lower()
   
                        if proceed2 == "y":
                            break  
                    
                    except ValueError:
                        print("無効な入力です。数値を入力してください。")

            popt = run_fit(model_name, initial_guess)
            if popt is not None:
                write_in_conf(ant30conf, popt, model_name)
            break
        
        else:
            print("無効な選択肢です。再度入力してください。")

#def run_fit(fitting_model, residual_func, model_name, initial_guess):
def run_fit(model_name, initial_guess):
    """
    フィッティング処理を実行する関数
    """
    # データの読み込み
    offset_L_path = find_offset_L(folder)
    offset_C_path = find_offset_C(folder)

    AZ, EL, dAZ_obs_L, dEL_obs_L = [], [], [], []                         # 輝線データ用
    AZ1, EL1, dAZ_obs_C, AZ2, EL2, dEL_obs_C = [], [], [], [], [], [] # 連続波データ用

    if offset_L_path:
        print("offset_L.txtが見つかりました。")
        ret = get_data_line(offset_L_path)
        if ret is None:
            print("Error! get_data_line()")
        else:
            AZ.extend(ret["AZ"].tolist())
            EL.extend(ret["EL"].tolist())
            dAZ_obs_L.extend(ret["dAZ"].tolist())
            dEL_obs_L.extend(ret["dEL"].tolist())

    if offset_C_path:
        print("offset_C.txtが見つかりました。")
        ret = get_data_continuum(offset_C_path)
        if ret is None:
            print("Eroor! get_data_continuum()")
        else:
            # AZ scan
            AZ1.extend(ret["AZ_1"].tolist())
            EL1.extend(ret["EL_1"].tolist())
            dAZ_obs_C.extend(ret["dAZ"].tolist())
            # EL scan
            AZ2.extend(ret["AZ_2"].tolist())
            EL2.extend(ret["EL_2"].tolist())
            dEL_obs_C.extend(ret["dEL"].tolist())

    if not offset_L_path and not offset_C_path:
        print("ファイルの読み込みに失敗しました。")
        return None

    # リストを np.array に変換
    AZ = np.array(AZ)
    EL = np.array(EL)
    dAZ_obs_L = np.array(dAZ_obs_L)
    dEL_obs_L = np.array(dEL_obs_L)

    AZ1 = np.array(AZ1)
    EL1 = np.array(EL1)
    AZ2 = np.array(AZ2)
    EL2 = np.array(EL2)
    dAZ_obs_C = np.array(dAZ_obs_C)
    dEL_obs_C = np.array(dEL_obs_C)

    # debug
    #print("Length of AZ:", len(AZ))
    #print("Length of EL:", len(EL))
    #print("Length of dAZ_obs_L:", len(dAZ_obs_L))
    #print("Length of dEL_obs_L:", len(dEL_obs_L))
    #print("Length of dAZ_obs_C:", len(dAZ_obs_C))
    #print("Length of dEL_obs_C:", len(dEL_obs_C))
    #print("AZ\n", AZ)
    #print("EL\n", EL)
    #print("dAZ_obs_L\n", dAZ_obs_L)
    #print("dEL_obs_L\n", dEL_obs_L)
    #print("dAZ_obs_C\n", dAZ_obs_C)
    #print("dEL_obs_C\n", dEL_obs_C)
    
    # モデルと残差関数の選択
    if model_name == '60cm_model':
        model_C = model_60cm_C
        model_L = model_60cm_L
        residuals_C = residuals_60cm_C
        residuals_L = residuals_60cm_L
        residuals_C_and_L = residuals_60cm_C_and_L
    elif model_name == '60cm_model_2':
        model_C = model_60cm_C_2
        model_L = model_60cm_L_2
        residuals_C = residuals_60cm_C_2
        residuals_L = residuals_60cm_L_2
        residuals_C_and_L = residuals_60cm_C_and_L_2
    elif model_name == 'optical_model':
        model_C = opt_model_C
        model_L = opt_model_L
        residuals_C = residuals_opt_C
        residuals_L = residuals_opt_L
        residuals_C_and_L = residuals_opt_C_and_L
    else:
        raise ValueError(f"Unknown model_name: {model_name}")


    if offset_L_path and not offset_C_path:
        print("輝線データのみ使用します")
        result = least_squares(residuals_L, initial_guess, args=(AZ, EL, dAZ_obs_L, dEL_obs_L))
        popt = result.x
        dAZ_fit_L, dEL_fit_L = model_L(popt, AZ, EL)
        rms_dAZ_L = np.sqrt(np.mean((dAZ_obs_L - dAZ_fit_L) ** 2)) * 3600
        rms_dEL_L = np.sqrt(np.mean((dEL_obs_L - dEL_fit_L) ** 2)) * 3600
        print(f"dAZ_rms: {rms_dAZ_L:.6f} \"")
        print(f"dEL_rms: {rms_dEL_L:.6f} \"")

        beforeRMS = 0
        afterRMS = 0

        for i in range(len(AZ)):
            # 二乗和でRMSを計算
            beforeRMS = np.sqrt(np.mean(dAZ_obs_L**2 + dEL_obs_L**2)) * 3600
            afterRMS = np.sqrt(np.mean((dAZ_fit_L - dAZ_obs_L)**2 + (dEL_fit_L - dEL_obs_L)**2)) * 3600

        beforeRMS = str(round(beforeRMS*3600, 2)) #deg -->- arcsec
        afterRMS = str(round(afterRMS*3600, 2)) #deg -->- arcsec

        beforeRMS = beforeRMS.rjust(6)
        afterRMS = afterRMS.rjust(6)

        print("観測結果のRMS　　　　　　　　:", beforeRMS, "\"")
        print("フィッティング結果のRMS　　　:", afterRMS, "\"")
        print("目標のRMS　　　　　　　　　　:  54    \"")

        # プロット実行
        plot_daz_del(dAZ_obs_L, dEL_obs_L, dAZ_fit_L - dAZ_obs_L, dEL_fit_L - dEL_obs_L, model_name)
        plot_subplots_L(AZ, EL, dAZ_obs_L, dAZ_fit_L, dEL_obs_L, dEL_fit_L, model_name)
        print("器差パラメーター\n",popt)


    elif offset_C_path and not offset_L_path:
        print("連続波データのみ使用します")
        result = least_squares(residuals_C, initial_guess, args=(AZ1, EL1, AZ2, EL2, dAZ_obs_C, dEL_obs_C))
        popt = result.x
        # debug
        #print("len(dAZ_obs_C): ", len(dAZ_obs_C))
        #print("len(AZ1): ", len(AZ1))
        #print("len(AZ2): ", len(AZ2))
        dAZ_fit_C, dEL_fit_C = model_C(popt, AZ1, EL1, AZ2, EL2)
        rms_dAZ_C = np.sqrt(np.mean((dAZ_obs_C - dAZ_fit_C) ** 2)) * 3600
        rms_dEL_C = np.sqrt(np.mean((dEL_obs_C - dEL_fit_C) ** 2)) * 3600
        print(f"dAZ_rms: {rms_dAZ_C:.6f} \"")
        print(f"dEL_rms: {rms_dEL_C:.6f} \"")

        beforeRMS = 0
        afterRMS = 0
        for i in range(len(AZ1)):
            beforeRMS = np.sqrt(np.mean(dAZ_obs_C**2 + dEL_obs_C**2)) * 3600
            afterRMS = np.sqrt(np.mean((dAZ_fit_C - dAZ_obs_C)**2 + (dEL_fit_C - dEL_obs_C)**2)) * 3600

        beforeRMS = str(round(beforeRMS*3600, 2)) #deg -->- arcsec
        afterRMS = str(round(afterRMS*3600, 2)) #deg -->- arcsec

        beforeRMS = beforeRMS.rjust(6)
        afterRMS = afterRMS.rjust(6)

        print("観測結果のRMS　　　　　　　　:", beforeRMS, "\"")
        print("フィッティング結果のRMS　　　:", afterRMS, "\"")
        print("目標のRMS　　　　　　　　　　:  54    \"")

        # プロット実行
        plot_daz_del(dAZ_obs_C, dEL_obs_C, dAZ_fit_C - dAZ_obs_C, dEL_fit_C - dEL_obs_C, model_name)
        #plot_subplots(AZ1, EL1, dAZ_obs_C, dAZ_fit_C, dEL_obs_C, dEL_fit_C, model_name)
        plot_subplots_C(AZ1, EL1, AZ2, EL2, dAZ_obs_C, dAZ_fit_C, dEL_obs_C, dEL_fit_C, model_name)
        print("器差パラメーター\n",popt)


    elif offset_L_path and offset_C_path:
        print("輝線データと連続波データを使用します")
        result = least_squares(residuals_C_and_L, initial_guess, args=(dAZ_obs_C, dEL_obs_C, AZ1, EL1, AZ2, EL2, dAZ_obs_L, dEL_obs_L, AZ, EL)) # 変更前

        popt = result.x
        dAZ_fit_C, dEL_fit_C = model_C(popt, AZ1, EL1, AZ2, EL2)
        dAZ_fit_L, dEL_fit_L = model_L(popt, AZ, EL)
        rms_dAZ_C = np.sqrt(np.mean((dAZ_obs_C - dAZ_fit_C) ** 2)) * 3600
        rms_dEL_C = np.sqrt(np.mean((dEL_obs_C - dEL_fit_C) ** 2)) * 3600
        rms_dAZ_L = np.sqrt(np.mean((dAZ_obs_L - dAZ_fit_L) ** 2)) * 3600
        rms_dEL_L = np.sqrt(np.mean((dEL_obs_L - dEL_fit_L) ** 2)) * 3600
        print(f"dAZ_rms: {rms_dAZ_L + rms_dAZ_C:.6f} \"")
        print(f"dEL_rms: {rms_dEL_L + rms_dEL_C:.6f} \"")

        rms_vals_obs = []
        rms_vals_fit = []

        for i in range(len(AZ)):  # 輝線データ
            rms_vals_obs.append(dAZ_obs_L[i] ** 2 + dEL_obs_L[i] ** 2)
            rms_vals_fit.append((dAZ_fit_L[i] - dAZ_obs_L[i]) ** 2 + (dEL_fit_L[i] - dEL_obs_L[i]) ** 2)

        for i in range(len(AZ1)):  # 連続波データ
            rms_vals_obs.append(dAZ_obs_C[i] ** 2 + dEL_obs_C[i] ** 2)
            rms_vals_fit.append((dAZ_fit_C[i] - dAZ_obs_C[i]) ** 2 + (dEL_fit_C[i] - dEL_obs_C[i]) ** 2)

        beforeRMS = np.sqrt(np.mean(rms_vals_obs)) * 3600
        afterRMS = np.sqrt(np.mean(rms_vals_fit)) * 3600

        beforeRMS = str(round(beforeRMS, 2)).rjust(6)
        afterRMS = str(round(afterRMS, 2)).rjust(6)

        print("観測結果のRMS　　　　　　　　:", beforeRMS, "\"")
        print("フィッティング結果のRMS　　　:", afterRMS, "\"")
        print("目標のRMS　　　　　　　　　　:  54    \"")

        # プロット実行
        dAZ_obs_all = np.concatenate((dAZ_obs_L, dAZ_obs_C))
        dEL_obs_all = np.concatenate((dEL_obs_L, dEL_obs_C))
        dAZ_fit_all = np.concatenate((dAZ_fit_L, dAZ_fit_C))
        dEL_fit_all = np.concatenate((dEL_fit_L, dEL_fit_C))
        # debug
        #print("len(AZ)+len(AZ1)+len(AZ2) = ",len(AZ)+len(AZ1))
        #print("len(dAZ_obs_L)+len(dAZ_obs_C) = ",len(dAZ_obs_L)+len(dAZ_obs_C))
        #print("len(dEL_fit_L)+len(dEL_fit_C) = ",len(dEL_obs_L)+len(dEL_fit_C))

        plot_daz_del(dAZ_obs_all, dEL_obs_all, dAZ_fit_all - dAZ_obs_all, dEL_fit_all - dEL_obs_all, model_name)
        plot_subplots_L_and_C(AZ, EL, AZ1, EL1, AZ2, EL2, dAZ_obs_all, dAZ_fit_all, dEL_obs_all, dEL_fit_all, model_name)

        print("器差パラメーター\n",popt)

        #save(AZ, EL, dAZ_obs, dAZ_fit, dEL_obs, dEL_fit, model_name)

    else:
        print("offset_L.txt または offset_C.txt が見つかりませんでした。")
        return None

    return popt


def find_offset_C(folder):
    """
    指定されたフォルダ内で offset_C.txt を再帰的に探す
    """
    base_folder = os.path.join(os.getcwd(), folder)  # カレントディレクトリからの相対パス
    for root, dirs, files in os.walk(base_folder):  # フォルダ内を再帰的に探索
        if "offset_C.txt" in files:  
            return os.path.join(root, "offset_C.txt")  # フルパスを返す
        else:
            print("offset_C.txt が見つかりません。")
    return None  


def find_offset_L(folder):
    """
    指定されたフォルダ内で offset_L.txt を再帰的に探す
    """
    base_folder = os.path.join(os.getcwd(), folder)  # カレントディレクトリからの相対パス
    for root, dirs, files in os.walk(base_folder):  # フォルダ内を再帰的に探索
        if "offset_L.txt" in files:  
            return os.path.join(root, "offset_L.txt")  # フルパスを返す
        else:
            print("offset_L.txt が見つかりません。")
    return None 


def write_in_conf(ant30conf, popt, model_name):
    """
    器差パラメーターを ant30_phaseC0.conf に自動書き込み
    """
    date = datetime.now().strftime('%Y/%m/%d %H:%M:%S')

    # ファイルの内容を一時的に保存
    with open(ant30conf, "r", encoding="utf-8") as file:
        old_data = file.readlines()

    # 新しく書き込む器差パラメーターの設定
    if model_name == "60cm_model":
        kisapara = [
            ('AntRadioInst0', popt[:4]),                     # B0, B1, B2, B3
            ('AntRadioInst1', [popt[4], popt[5], 0.0, 0.0]), # B4, B5, 0,  0
            ('AntRadioInst2', [0.0, 0.0, 0.0, 0.0])          # 0,  0,  0,  0
        ]
    elif model_name == "60cm_model_2":
        kisapara = [
            ('AntRadioInst0', popt[:4]),                     # B0, B1, B2, B3
            ('AntRadioInst1', popt[4:8]),                    # B4, B5, B6, B7
            ('AntRadioInst2', [popt[8], popt[9], 0.0, 0.0])  # B8, B9,  0,  0
        ]
    elif model_name == "optical_model":
        kisapara = [
            ('AntRadioInst0', popt[:5]),                     # A1, A2, A3, A4, A5
            ('AntRadioInst1', popt[5:10]),                   # A6, A7, A8, A9, A10
            ('AntRadioInst2', popt[10:15])                   # A11, A12, A13, A14, A15
        ]
    else:
        print("無効なモデル名です。")
        return

    # 書き込む内容を表示
    for name, values in kisapara:
        formatted_values = '\t'.join(f'{v:.9f}' for v in values)
        print(f'{name}\t{formatted_values}')
    
    proceed = input("\nこのまま ant30_phaseC0.conf に書き込みますか？：[y]es / [n]o: ").strip().lower()

    if proceed == 'y':
        with open(ant30conf, "w", encoding="utf-8") as p:
            # 既存の `AntRadioInst` をコメントアウト
            for line in old_data:
                if line.startswith('AntRadioInst0') or line.startswith('AntRadioInst1') or line.startswith('AntRadioInst2'):
                    p.write("#" + line)  
                else:
                    p.write(line) 

            # 新しい器差パラメーターの書き込み
            p.write("\n") 
            p.write(f'# {model_name}\t{date}\n')
            for name, values in kisapara:
                p.write(f'{name}\t' + '\t'.join(f'{v:.9f}' for v in values) + '\n')

        print("\nant30_phaseC0.conf に書き込みました。")
    else:
        print("\n書き込みをキャンセルしました。")



def read_old_kisapara_from_conf(model_name):
    """
    ant30_phaseC0.confにある前回の器差パラを読み取ってリストに格納。
    これをフィッティングの初期パラメーターにする。
    AntRadioInst0, 1, 2 を探し、kisapara_old_list に左上から順に詰める。
    """
    kisapara_old_list = []

    try:
        with open(ant30conf, 'r', encoding='utf-8') as file:
            log_lines = file.readlines()
        
        for line in log_lines:
            if model_name == "60cm_model":
                if line.startswith("AntRadioInst0"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:5]])  
                elif line.startswith("AntRadioInst1"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:3]])  
            
            elif model_name == "60cm_model_2":
                if line.startswith("AntRadioInst0"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:5]]) 
                elif line.startswith("AntRadioInst1"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:5]])  
                elif line.startswith("AntRadioInst2"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:3]])  

            elif model_name == "optical_model":
                if line.startswith("AntRadioInst0"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:6]])  
                elif line.startswith("AntRadioInst1"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:6]]) 
                elif line.startswith("AntRadioInst2"):
                    match = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    kisapara_old_list.extend([float(num) for num in match[1:6]]) 

    except FileNotFoundError:
        print(f"Error: {ant30conf} が見つかりません。")
    except Exception as e:
        print(f"Error: {ant30conf} から器差パラメーターの読み取りに失敗しました。{e}")
    # debug
    #print("kisapara_old_list:", len(kisapara_old_list))
    #print(kisapara_old_list)
    return kisapara_old_list


def get_data_line(offset_file):
    """
    輝線ポインティング結果 offset_L.txtから、AZ, EL, dAZ, dEL を読み取って辞書に保存
    """
    ret = {}

    data = pd.read_csv(offset_file,skiprows=1, header=None, names=["AZ", "EL", "dAZ", "dEL"]).to_numpy()
    ret["AZ"], ret["EL"], ret["dAZ"], ret["dEL"] = data[:, 0], data[:, 1], data[:, 2],data[:, 3]

    return ret


def get_data_continuum(offset_file):
    """
    rp_peaksearch.pyの出力結果を読み取る。
    連続波ポインティング結果 offset_C.txtから、AZ_1, EL_1, dAZ, AZ_2, EL_2, dEL を読み取って辞書に保存
    """
    ret = {}

    data = pd.read_csv(offset_file,skiprows=1, sep="\t",header=None, names=["AZ_1", "EL_1", "dAZ", "AZ_2", "EL_2","dEL"]).to_numpy()
    ret["AZ_1"], ret["EL_1"], ret["dAZ"], ret["AZ_2"], ret["EL_2"], ret["dEL"] = data[:, 0], data[:, 1], data[:, 2],data[:, 3], data[:, 4], data[:, 5]

    return ret

def get_result_data(result_file):
    """
    result_*_model.txtから、AZ, EL, dAZ_before, dEL_before, dAZ_after, dEL_after を読み取って辞書に保存
    """
    ret = {}

    data = pd.read_csv(result_file, skiprows=1, header=None, names=["AZ", "EL", "dAZ_obs", "dEL_obs", "dAZ_fit", "dEL_fit"]).to_numpy()
    ret["AZ"], ret["EL"], ret["dAZ_obs"], ret["dEL_obs"], ret["dAZ_fit"], ret["dEL_fit"] = data[:, 0], data[:, 1], data[:, 2],data[:, 3], data[:, 4], data[:, 5]

    return ret

##################################################################################### 60 cm model
def model_60cm_L(B, AZ, EL):
    """
    60cm telescope 器差モデル（Nakajima et al. 2007）
    輝線データ用
    """
    AZ_rad = np.radians(AZ)
    EL_rad = np.radians(EL)
    B0, B1, B2, B3, B4, B5 = B
    
    dAZ_fit_L = B0 * np.sin(AZ_rad - EL_rad) + B1 * np.cos(AZ_rad - EL_rad) + B2 + B4 * np.cos(EL_rad) - B5 * np.sin(EL_rad)
    dEL_fit_L = B0 * np.cos(AZ_rad - EL_rad) - B1 * np.sin(AZ_rad - EL_rad) + B3 + B4 * np.sin(EL_rad) + B5 * np.cos(EL_rad)
    
    return dAZ_fit_L, dEL_fit_L

def model_60cm_C(B, AZ1, EL1, AZ2, EL2):
    """
    60cm telescope 器差モデル（Nakajima et al. 2007）
    連続波データ用
    """
    AZ1 = np.radians(AZ1)
    EL1 = np.radians(EL1)
    AZ2 = np.radians(AZ2)
    EL2 = np.radians(EL2)
    B0, B1, B2, B3, B4, B5 = B

    dAZ_fit_C = B0 * np.sin(AZ1 - EL1) + B1 * np.cos(AZ1 - EL1) + B2 + B4 * np.cos(EL1) - B5 * np.sin(EL1)
    dEL_fit_C = B0 * np.cos(AZ2 - EL2) - B1 * np.sin(AZ2 - EL2) + B3 + B4 * np.sin(EL2) + B5 * np.cos(EL2)

    return dAZ_fit_C, dEL_fit_C

def residuals_60cm_L(B, AZ, EL, dAZ_obs, dEL_obs):
    """
    60cm model 用の残差を計算する関数
    輝線データ用
    """
    dAZ_fit, dEL_fit = model_60cm_L(B, AZ, EL)
    
    # 観測データの標準偏差でスケーリング
    dAZ_std = np.std(dAZ_obs)
    dEL_std = np.std(dEL_obs)
    residuals_dAZ = (dAZ_obs - dAZ_fit) / dAZ_std
    residuals_dEL = (dEL_obs - dEL_fit) / dEL_std

    return np.concatenate([residuals_dAZ, residuals_dEL])

def residuals_60cm_C(B, AZ1, EL1, AZ2, EL2, dAZ_obs, dEL_obs):
    """
    60cm model 用の残差を計算する関数
    連続波データ用
    """
    dAZ_fit, dEL_fit = model_60cm_C(B, AZ1, EL1, AZ2, EL2)
    
    # 観測データの標準偏差でスケーリング
    dAZ_std = np.std(dAZ_obs)
    dEL_std = np.std(dEL_obs)
    residuals_dAZ = (dAZ_obs - dAZ_fit) / dAZ_std
    residuals_dEL = (dEL_obs - dEL_fit) / dEL_std

    return np.concatenate([residuals_dAZ, residuals_dEL])


def residuals_60cm_C_and_L(B, dAZ_obs_C, dEL_obs_C, AZ1, EL1, AZ2, EL2, dAZ_obs_L, dEL_obs_L, AZ, EL):
    if len(B) != 6:
        raise ValueError("Parameter B must contain exactly 6 elements.")
    # 連続波データの残差
    dAZ_fit_C, dEL_fit_C = model_60cm_C(B, AZ1, EL1, AZ2, EL2)
    if len(dAZ_obs_C) != len(dAZ_fit_C) or len(dEL_obs_C) != len(dEL_fit_C):
        raise ValueError("Continuous wave data dimensions do not match the model output.")    
    residuals_dAZ_C = dAZ_obs_C - dAZ_fit_C
    residuals_dEL_C = dEL_obs_C - dEL_fit_C
    
    # 輝線データの残差
    dAZ_fit_L, dEL_fit_L = model_60cm_L(B, AZ, EL)
    if len(dAZ_obs_L) != len(dAZ_fit_L) or len(dEL_obs_L) != len(dEL_fit_L):
        raise ValueError("Line data dimensions do not match the model output.")
    residuals_dAZ_L = dAZ_obs_L - dAZ_fit_L
    residuals_dEL_L = dEL_obs_L - dEL_fit_L

    return np.concatenate([residuals_dAZ_C, residuals_dEL_C, residuals_dAZ_L, residuals_dEL_L])


############################################################################# 60 cm model 改良版
def model_60cm_L_2(B, AZ, EL): 
    """
    60cm モデルの改良版.　器差パラメータ10個　
    輝線データ用
    """
    AZ_rad = np.radians(AZ)
    EL_rad = np.radians(EL)
    B0, B1, B2, B3, B4, B5, B6, B7, B8, B9 = B
    
    dAZ = B1 * np.cos(AZ_rad - EL_rad) - B0 * np.sin(AZ_rad - EL_rad) + B2 + B4 * np.cos(EL_rad) - B5 * np.sin(EL_rad) + B6 * np.cos(AZ_rad) - B7 * np.sin(AZ_rad) + B8 * np.cos(AZ_rad + EL_rad) - B9* np.sin(AZ_rad + EL_rad)
    dEL = B1 * np.sin(EL_rad - EL_rad) + B0 * np.cos(AZ_rad - EL_rad) + B3 - B4 * np.sin(EL_rad) + B5 * np.cos(EL_rad) + B6 * np.sin(AZ_rad) + B7 * np.cos(AZ_rad) + B8 * np.sin(AZ_rad + EL_rad) + B9* np.cos(AZ_rad + EL_rad)
    
    return dAZ, dEL

def model_60cm_C_2(B, AZ1, EL1, AZ2, EL2): 
    """
    60cm モデルの改良版.　器差パラメータ10個　]
    連続波データ用
    """
    AZ1 = np.radians(AZ1)
    EL1 = np.radians(EL1)
    AZ2 = np.radians(AZ2)
    EL2 = np.radians(EL2)
    B0, B1, B2, B3, B4, B5, B6, B7, B8, B9 = B
    
    dAZ = B1 * np.cos(AZ1 - EL1) - B0 * np.sin(AZ1 - EL1) + B2 + B4 * np.cos(EL1) - B5 * np.sin(EL1) + B6 * np.cos(AZ1) - B7 * np.sin(AZ1) + B8 * np.cos(AZ1 + EL1) - B9* np.sin(AZ1 + EL1)
    dEL = B1 * np.sin(EL2 - EL2) + B0 * np.cos(AZ2 - EL2) + B3 - B4 * np.sin(EL2) + B5 * np.cos(EL2) + B6 * np.sin(AZ2) + B7 * np.cos(AZ2) + B8 * np.sin(AZ2 + EL2) + B9* np.cos(AZ2 + EL2)
    
    return dAZ, dEL

def residuals_60cm_L_2(B, AZ, EL, dAZ_obs, dEL_obs):
    """
    60cm model 改良版 用の残差を計算する関数　輝線データ用
    """
    dAZ_fit, dEL_fit = model_60cm_L_2(B, AZ, EL)
    # 観測データの標準偏差でスケーリング
    dAZ_std = np.std(dAZ_obs)
    dEL_std = np.std(dEL_obs)
    residuals_dAZ = (dAZ_obs - dAZ_fit) / dAZ_std
    residuals_dEL = (dEL_obs - dEL_fit) / dEL_std

    return np.concatenate([residuals_dAZ, residuals_dEL])

def residuals_60cm_C_2(B, AZ1, EL1, AZ2, EL2, dAZ_obs, dEL_obs):
    """
    60cm model 改良版 用の残差を計算する関数　連続波データ用
    """
    dAZ_fit, dEL_fit = model_60cm_C_2(B, AZ1, EL1, AZ2, EL2)
    # 観測データの標準偏差でスケーリング
    dAZ_std = np.std(dAZ_obs)
    dEL_std = np.std(dEL_obs)
    residuals_dAZ = (dAZ_obs - dAZ_fit) / dAZ_std
    residuals_dEL = (dEL_obs - dEL_fit) / dEL_std

    return np.concatenate([residuals_dAZ, residuals_dEL])

def residuals_60cm_C_and_L_2(B, dAZ_obs_C, dEL_obs_C, AZ1, EL1, AZ2, EL2, dAZ_obs_L, dEL_obs_L, AZ, EL):
    if len(B) != 10:
        raise ValueError("Parameter B must contain exactly 10 elements.")
    # 連続波データの残差
    dAZ_fit_C, dEL_fit_C = model_60cm_C_2(B, AZ1, EL1, AZ2, EL2)
    if len(dAZ_obs_C) != len(dAZ_fit_C) or len(dEL_obs_C) != len(dEL_fit_C):
        raise ValueError("Continuous wave data dimensions do not match the model output.")    
    residuals_dAZ_C = dAZ_obs_C - dAZ_fit_C
    residuals_dEL_C = dEL_obs_C - dEL_fit_C
    
    # 輝線データの残差
    dAZ_fit_L, dEL_fit_L = model_60cm_L_2(B, AZ, EL)
    if len(dAZ_obs_L) != len(dAZ_fit_L) or len(dEL_obs_L) != len(dEL_fit_L):
        raise ValueError("Line data dimensions do not match the model output.")
    residuals_dAZ_L = dAZ_obs_L - dAZ_fit_L
    residuals_dEL_L = dEL_obs_L - dEL_fit_L

    return np.concatenate([residuals_dAZ_C, residuals_dEL_C, residuals_dAZ_L, residuals_dEL_L])


###################################################################################### optical model
def opt_model_L(A, AZ, EL):
    """
    光学ポインティングで使用していた式 (Koyama master thesis 2021)
    器差パラメーター15個　輝線データ用
    """
    AZ_rad = np.radians(AZ)
    EL_rad = np.radians(EL)
    A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12, A13, A14, A15 = A
    
    dAZ = A1 + A2*np.cos(AZ_rad)*np.tan(EL_rad) + A3*np.sin(AZ_rad)*np.tan(EL_rad) + A4*np.tan(EL_rad) + A5/np.cos(EL_rad) 
    + A8*np.cos(AZ_rad) + A9*np.sin(AZ_rad) + A12*np.cos(AZ_rad)*np.cos(EL_rad)
    + A13*np.cos(AZ_rad)*np.sin(EL_rad) + A14*np.sin(AZ_rad)*np.cos(EL_rad) + A15*EL
    
    dEL = -A2*np.sin(AZ_rad) + A3*np.cos(AZ_rad) + A6 + A7*np.cos(EL_rad) + A10*np.cos(AZ_rad) +A11*np.sin(AZ_rad)
    
    return dAZ, dEL

def opt_model_C(A, AZ1, EL1, AZ2, EL2):
    """
    光学ポインティングで使用していた式 (Koyama master thesis 2021)
    器差パラメーター15個　連続波データ用
    """
    AZ1 = np.radians(AZ1)
    EL1_rad = np.radians(EL1)
    AZ2 = np.radians(AZ2)
    EL2 = np.radians(EL2)
    A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12, A13, A14, A15 = A
    
    dAZ = A1 + A2*np.cos(AZ1)*np.tan(EL1_rad) + A3*np.sin(AZ1)*np.tan(EL1_rad) + A4*np.tan(EL1_rad) + A5/np.cos(EL1_rad) 
    + A8*np.cos(AZ1) + A9*np.sin(AZ1) + A12*np.cos(AZ1)*np.cos(EL1_rad)
    + A13*np.cos(AZ1)*np.sin(EL1_rad) + A14*np.sin(AZ1)*np.cos(EL1_rad) + A15*EL1
    
    dEL = -A2*np.sin(AZ2) + A3*np.cos(AZ2) + A6 + A7*np.cos(EL2) + A10*np.cos(AZ2) +A11*np.sin(AZ2)
    
    return dAZ, dEL

def residuals_opt_L(A, AZ, EL, dAZ_obs, dEL_obs):
    """
    Opical pointing model 用の残差を計算する関数　輝線データ用
    """
    dAZ_fit, dEL_fit = opt_model_L(A, AZ, EL)
    # 観測データの標準偏差でスケーリング
    dAZ_std = np.std(dAZ_obs)
    dEL_std = np.std(dEL_obs)
    residuals_dAZ = (dAZ_obs - dAZ_fit) / dAZ_std
    residuals_dEL = (dEL_obs - dEL_fit) / dEL_std    

    return np.concatenate([residuals_dAZ, residuals_dEL])

def residuals_opt_C(A, AZ1, EL1, AZ2, EL2, dAZ_obs, dEL_obs):
    """
    Opical pointing model 用の残差を計算する関数　連続波データ用
    """
    dAZ_fit, dEL_fit = opt_model_C(A, AZ1, EL1, AZ2, EL2)
    # 観測データの標準偏差でスケーリング
    dAZ_std = np.std(dAZ_obs)
    dEL_std = np.std(dEL_obs)
    residuals_dAZ = (dAZ_obs - dAZ_fit) / dAZ_std
    residuals_dEL = (dEL_obs - dEL_fit) / dEL_std    

    return np.concatenate([residuals_dAZ, residuals_dEL])

def residuals_opt_C_and_L(B, dAZ_obs_C, dEL_obs_C, AZ1, EL1, AZ2, EL2, dAZ_obs_L, dEL_obs_L, AZ, EL):
    if len(B) != 15:
        raise ValueError("Parameter B must contain exactly 15 elements.")
    # 連続波データの残差
    dAZ_fit_C, dEL_fit_C = opt_model_C(B, AZ1, EL1, AZ2, EL2)
    if len(dAZ_obs_C) != len(dAZ_fit_C) or len(dEL_obs_C) != len(dEL_fit_C):
        raise ValueError("Continuous wave data dimensions do not match the model output.")    
    residuals_dAZ_C = dAZ_obs_C - dAZ_fit_C
    residuals_dEL_C = dEL_obs_C - dEL_fit_C
    
    # 輝線データの残差
    dAZ_fit_L, dEL_fit_L = opt_model_L(B, AZ, EL)
    if len(dAZ_obs_L) != len(dAZ_fit_L) or len(dEL_obs_L) != len(dEL_fit_L):
        raise ValueError("Line data dimensions do not match the model output.")
    residuals_dAZ_L = dAZ_obs_L - dAZ_fit_L
    residuals_dEL_L = dEL_obs_L - dEL_fit_L

    return np.concatenate([residuals_dAZ_C, residuals_dEL_C, residuals_dAZ_L, residuals_dEL_L])

##################################################################################################  other model
#def model_60cm_3(B, AZ, EL):
#    """
#    ant30/instrument.cppにあったモデル式
#    """
#    AZ_rad = np.radians(AZ)
#    EL_rad = np.radians(EL)
#    B0, B1, B2, B3, B4, B5 = B
    
#    dAZ = B0 * np.sin(AZ_rad + EL_rad) + B1 * np.cos(AZ_rad + EL_rad) + B2 + B4 * np.cos(EL_rad) + B5 * np.sin(EL_rad)
#    dEL = B0 * np.cos(AZ_rad + EL_rad) - B1 * np.sin(AZ_rad + EL_rad) + B3 - B4 * np.sin(EL_rad) + B5 * np.cos(EL_rad)
    
#    return dAZ, dEL

#def model_60cm_4(B, AZ, EL):
#    """
#    ant30/instrument.cppにあったモデル式 iwata master thesis 200?年
#    """
#    AZ_rad = np.radians(AZ)
#    EL_rad = np.radians(EL)
#    B0, B1, B2, B3 = B
    
#    dAZ = B0 * np.sin(AZ_rad - EL_rad) + B1 * np.cos(AZ_rad - EL_rad) + B2 
#    dEL = B0 * np.cos(AZ_rad - EL_rad) - B1 * np.sin(AZ_rad - EL_rad) + B3 
    
#    return dAZ, dEL


# dAZ vs dEL の円プロット
def plot_daz_del(dAZ_obs, dEL_obs, dAZ_fit, dEL_fit, model_name):
    fig, ax = plt.subplots()

    sc01 = ax.scatter(dAZ_obs, dEL_obs, c="b", label="before")
    sc02 = ax.scatter(dAZ_fit, dEL_fit, c="c", marker="x", label="after")

    circle1 = plt.Circle((0, 0), 0.3, fill=False, color="r")
    circle2 = plt.Circle((0, 0), 0.15, fill=False, color="r", linestyle="dashed")
    circle3 = plt.Circle((0, 0), 0.015, fill=False, color="r", linestyle=":")

    ax.add_artist(circle1)
    ax.add_artist(circle2)
    ax.add_artist(circle3)

    ax.set(xlabel=r"dAZ [deg]", ylabel=r"dEL [deg]")
    ax.grid(True)
    ax.set_xlim([-0.5, 0.5])
    ax.set_ylim([-0.5, 0.5])
    ax.set_aspect(1)
    ax.legend([circle1, circle2, circle3, sc01, sc02], ["18'", "9'", "0.9'", "before", "after"])
    ax.axhline(0, color='black')
    ax.axvline(0, color='black')

    plt.tight_layout()
    plt.savefig(f'result1_{model_name}.png')
    plt.show()

# 輝線データ用プロット
# AZ vs dAZ, AZ vs dEL, EL vs dAZ, EL vs dEL のプロット
def plot_subplots_L(AZ, EL, dAZ_obs, dAZ_fit, dEL_obs, dEL_fit, model_name):
    fig, ax = plt.subplots(2, 2, figsize=(10, 6))

    ax[0][0].scatter(AZ, dAZ_obs, c="red", label="dAZ_obs")
    ax[0][0].scatter(AZ, dAZ_fit, c="m", marker="x", label="dAZ_fit")
    ax[0][0].scatter(AZ, dAZ_fit - dAZ_obs, c="darkmagenta",label="residuals dAZ", s=10)    
    ax[0][0].set(xlabel=r"AZ [deg]", ylabel=r"dAZ [deg]")
    ax[0][0].legend()
    ax[0][0].set_xlim([0, 360])
    ax[0][0].set_xticks([0, 60, 120, 180, 240, 300, 360])
    ax[0][0].axhline(0, color='black')

    ax[0][1].scatter(AZ, dEL_obs, c="blue", label="dEL_obs")
    ax[0][1].scatter(AZ, dEL_fit, c="c", marker="x", label="dEL_fit")
    ax[0][1].scatter(AZ, dEL_fit - dEL_obs, c="darkblue",label="residuals dEL",s=10)    
    ax[0][1].set(xlabel=r"AZ [deg]", ylabel=r"dEL [deg]")
    ax[0][1].legend()
    ax[0][1].set_xlim([0, 360])
    ax[0][1].set_xticks([0, 60, 120, 180, 240, 300, 360])
    ax[0][1].axhline(0, color='black')

    ax[1][0].scatter(EL, dAZ_obs, c="red", label="dAZ_obs")
    ax[1][0].scatter(EL, dAZ_fit, c="m", marker="x", label="dAZ_fit")
    ax[1][0].scatter(EL, dAZ_fit - dAZ_obs, c="darkmagenta",label="residuals dAZ",s=10) 
    ax[1][0].set(xlabel=r"EL [deg]", ylabel=r"dAZ [deg]")
    ax[1][0].legend()
    ax[1][0].set_xlim([0, 90])
    ax[1][0].set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax[1][0].axhline(0, color='black')

    ax[1][1].scatter(EL, dEL_obs, c="blue", label="dEL_obs")
    ax[1][1].scatter(EL, dEL_fit, c="c", marker="x", label="dEL_fit")
    ax[1][1].scatter(EL, dEL_fit - dEL_obs, c="darkblue",label="residuals dEL",s=10)   
    ax[1][1].set(xlabel=r"EL [deg]", ylabel=r"dEL [deg]")
    ax[1][1].legend()
    ax[1][1].set_xlim([0, 90])
    ax[1][1].set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax[1][1].axhline(0, color='black')

    plt.tight_layout()
    plt.savefig(f'result2_{model_name}_L.png')
    plt.show()

# 連続波データ専用プロット
def plot_subplots_C(AZ1, EL1, AZ2, EL2, dAZ_obs, dAZ_fit, dEL_obs, dEL_fit, model_name):
    fig, ax = plt.subplots(2, 2, figsize=(10, 6))

    ax[0][0].scatter(AZ1, dAZ_obs, c="red", label="dAZ_obs")
    ax[0][0].scatter(AZ1, dAZ_fit, c="m", marker="x", label="dAZ_fit")
    ax[0][0].scatter(AZ1, dAZ_fit - dAZ_obs, c="darkmagenta",label="residuals dAZ", s=10)    
    ax[0][0].set(xlabel=r"AZ1 [deg]", ylabel=r"dAZ [deg]")
    ax[0][0].legend()
    ax[0][0].set_title("AZ scan")
    ax[0][0].set_xlim([0, 360])
    ax[0][0].set_xticks([0, 60, 120, 180, 240, 300, 360])
    ax[0][0].axhline(0, color='black')

    ax[0][1].scatter(AZ2, dEL_obs, c="blue", label="dEL_obs")
    ax[0][1].scatter(AZ2, dEL_fit, c="c", marker="x", label="dEL_fit")
    ax[0][1].scatter(AZ2, dEL_fit - dEL_obs, c="darkblue",label="residuals dEL",s=10)    
    ax[0][1].set(xlabel=r"AZ2 [deg]", ylabel=r"dEL [deg]")
    ax[0][1].legend()
    ax[0][1].set_title("EL scan")
    ax[0][1].set_xlim([0, 360])
    ax[0][1].set_xticks([0, 60, 120, 180, 240, 300, 360])
    ax[0][1].axhline(0, color='black')

    ax[1][0].scatter(EL1, dAZ_obs, c="red", label="dAZ_obs")
    ax[1][0].scatter(EL1, dAZ_fit, c="m", marker="x", label="dAZ_fit")
    ax[1][0].scatter(EL1, dAZ_fit - dAZ_obs, c="darkmagenta",label="residuals dAZ",s=10) 
    ax[1][0].set(xlabel=r"EL1 [deg]", ylabel=r"dAZ [deg]")
    ax[1][0].legend()
    ax[1][0].set_title("AZ scan")
    ax[1][0].set_xlim([0, 90])
    ax[1][0].set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax[1][0].axhline(0, color='black')

    ax[1][1].scatter(EL2, dEL_obs, c="blue", label="dEL_obs")
    ax[1][1].scatter(EL2, dEL_fit, c="c", marker="x", label="dEL_fit")
    ax[1][1].scatter(EL2, dEL_fit - dEL_obs, c="darkblue",label="residuals dEL",s=10)   
    ax[1][1].set(xlabel=r"EL2 [deg]", ylabel=r"dEL [deg]")
    ax[1][1].legend()
    ax[1][1].set_title("EL scan")
    ax[1][1].set_xlim([0, 90])
    ax[1][1].set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax[1][1].axhline(0, color='black')

    plt.tight_layout()
    plt.savefig(f'result2_{model_name}_C.png')
    plt.show()

# 輝線＋連続波データ用プロット
def plot_subplots_L_and_C(AZ, EL, AZ1, EL1, AZ2, EL2, dAZ_obs, dAZ_fit, dEL_obs, dEL_fit, model_name):
    fig, ax = plt.subplots(2, 2, figsize=(10, 6))

    AZ_all_az_scan = np.concatenate((AZ, AZ1))
    EL_all_az_scan = np.concatenate((EL, EL1))
    AZ_all_el_scan = np.concatenate((AZ, AZ2))
    EL_all_el_scan = np.concatenate((EL, EL2))

    ax[0][0].scatter(AZ_all_az_scan, dAZ_obs, c="red", label="dAZ_obs")
    ax[0][0].scatter(AZ_all_az_scan, dAZ_fit, c="m", marker="x", label="dAZ_fit")
    ax[0][0].scatter(AZ_all_az_scan, dAZ_fit - dAZ_obs, c="darkmagenta",label="residuals dAZ", s=10)    
    ax[0][0].set(xlabel=r"AZ [deg]", ylabel=r"dAZ [deg]")
    ax[0][0].legend()
    ax[0][0].set_xlim([0, 360])
    ax[0][0].set_xticks([0, 60, 120, 180, 240, 300, 360])
    ax[0][0].axhline(0, color='black')

    ax[0][1].scatter(AZ_all_el_scan, dEL_obs, c="blue", label="dEL_obs")
    ax[0][1].scatter(AZ_all_el_scan, dEL_fit, c="c", marker="x", label="dEL_fit")
    ax[0][1].scatter(AZ_all_el_scan, dEL_fit - dEL_obs, c="darkblue",label="residuals dEL",s=10)    
    ax[0][1].set(xlabel=r"AZ [deg]", ylabel=r"dEL [deg]")
    ax[0][1].legend()
    ax[0][1].set_xlim([0, 360])
    ax[0][1].set_xticks([0, 60, 120, 180, 240, 300, 360])
    ax[0][1].axhline(0, color='black')

    ax[1][0].scatter(EL_all_az_scan, dAZ_obs, c="red", label="dAZ_obs")
    ax[1][0].scatter(EL_all_az_scan, dAZ_fit, c="m", marker="x", label="dAZ_fit")
    ax[1][0].scatter(EL_all_az_scan, dAZ_fit - dAZ_obs, c="darkmagenta",label="residuals dAZ",s=10) 
    ax[1][0].set(xlabel=r"EL [deg]", ylabel=r"dAZ [deg]")
    ax[1][0].legend()
    ax[1][0].set_xlim([0, 90])
    ax[1][0].set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax[1][0].axhline(0, color='black')

    ax[1][1].scatter(EL_all_el_scan, dEL_obs, c="blue", label="dEL_obs")
    ax[1][1].scatter(EL_all_el_scan, dEL_fit, c="c", marker="x", label="dEL_fit")
    ax[1][1].scatter(EL_all_el_scan, dEL_fit - dEL_obs, c="darkblue",label="residuals dEL",s=10)   
    ax[1][1].set(xlabel=r"EL [deg]", ylabel=r"dEL [deg]")
    ax[1][1].legend()
    ax[1][1].set_xlim([0, 90])
    ax[1][1].set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax[1][1].axhline(0, color='black')

    plt.tight_layout()
    plt.savefig(f'result2_{model_name}_L_and_C.png')
    plt.show()


def save(AZ, EL, dAZ_obs, dAZ_fit, dEL_obs, dEL_fit, model_name):
    with open(f"result_{model_name}.txt", "w") as f:
        f.write("AZ [deg], EL [deg], dAZ_before [deg], dEL_before [deg], dAZ_after [deg], dEL_after [deg]\n")
        data = np.column_stack((AZ, EL, dAZ_obs, dEL_obs, dAZ_fit, dEL_fit))
        for row in data:
            f.write(f"{row[0]:.6f},{row[1]:.6f},{row[2]:.6f},{row[3]:.6f},{row[4]:.6f},{row[5]:.6f}\n")


if __name__ == '__main__':
    main()