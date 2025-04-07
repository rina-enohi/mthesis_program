#!python3

import numpy as np
import pandas as pd
import datetime
import re
import datetime
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
import scipy
from scipy import signal
from scipy import interpolate

"""
ant30ログ、アンテナログ、パワーメーターログから、横軸：スキャンオフセット、縦軸：輝度温度T_B
のプロットをscan sequenceごとに表示させるプログラム。
必要なファイルはant30logとpowerlogのみ。

想定するスキャンのセットパターンは、
SetPattern      R,A,1,2
R, OFF点が1回ずつ、ON点は十字なので2回ずつ。（各SetNumberごとのT_B 計算用に必要）
Rは1つの観測テーブルで1回あればよい。

Set Patternを何回繰り返すかを指定するSetNumberはいくつでもよい。

次に実行する、rp_peaksearch.pyの解析用にプロット結果を１つのテキストファイル(ant30-2degsn-2024*.txt)に保存

閾値の線はinteractiveモードで手動で動かせる。
"""


def get_azel_scanoffset_ant30log(filename,linemargin=0,starting_keyword='(Az, El) ='):
    """
    ant30ログからdate, timestamp, AZ, EL, AZ_scanoffset, EL_scanoffsetを取得して辞書で保存。
    np.arrayに変換。
    linemerginのところは要変更。
    """
    ret = {}

    # file reading
    datalines = ''
    with open(filename)as f:
        datalines= f.readlines()
        pass

    # get target-line region
    tmp = np.where([starting_keyword in d for d in datalines])[0]
    lnbgn = tmp[0] - linemargin
    lnend = tmp[-1] + linemargin
    
    # get azel lines
    dl_ri = np.array([l.replace('\n','').replace(',','').replace('[','').replace(']','').replace('(','').replace(')','').split(' ') for l in datalines[lnbgn:lnend] if '(Az, El) =' in l])

    # convert line strings to azel or time
    dt = np.array([datetime.datetime.strptime(' '.join(x.split('-')[:2]),'%Y/%m/%d %H:%M:%S.%f') for x in dl_ri[:,0]])
    ts = np.array([x.timestamp() for x in dt])

    AZ = np.array([float(x) for x in dl_ri[:,4]]) 
    EL = np.array([float(x) for x in dl_ri[:,5]]) 
    AZ_scanoffset = np.array([float(x) for x in dl_ri[:,9]]) 
    EL_scanoffset = np.array([float(x) for x in dl_ri[:,10]]) 

    ret['AZ'] = AZ
    ret['EL'] = EL
    ret['AZ_scanoffset'] = AZ_scanoffset
    ret['EL_scanoffset'] = EL_scanoffset
    ret['date'] = dt
    ret['timestamp'] = ts
    ret['fn'] = '.'.join(filename.split('/')[-1].split('.')[:-1])

    return ret
    

def get_powerdata(filename):
    """
    パワーメーターログから、date, timestamp, power[dBm]を抽出し、辞書に格納しnp.array形式で保存。
    """
    ret = {}

    spa_pd = pd.read_csv(filename, sep='\t', header=None, names=['date','power'])
    ret['date'] = np.array([datetime.datetime.strptime(x[:25],'[%Y/%m/%d-%H:%M:%S.%f]') for x in spa_pd.date])
    ret['timestamp'] = np.array([x.timestamp() for x in ret['date']])
    ret['power'] = np.array(spa_pd.power)
    ret['fn'] = '.'.join(filename.split('/')[-1].split('.')[:-1])

    return ret


def extract_SetNumber(ant30log):
    """
    ant30ログからSetNumberを抽出する
    """
    SetNumber = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            SetNumber_match = re.search(r'SetNumber\s+(\d+)', line)

            if SetNumber_match:
                SetNumber = SetNumber_match.group(1)
                
    return SetNumber  

def extract_ON_time_from_ant30(ant30log):
    """
    ant30logからon開始時のon_start_timeとON終了時刻on_end_timeをdatetimeに変換し、辞書に保存。
    クロススキャンの場合、OnOffTimeはずれるので使わない。
    """
    ret = {}

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    count = 1 

    for line in log_lines:
        if '# On-Point  Integ start' in line:  # 助走分も含める        
            time_match = re.search(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})', line)
            if time_match:
                on_time_str = time_match.group(1)
                on_start_time = datetime.datetime.strptime(on_time_str, "%Y/%m/%d-%H:%M:%S.%f")

        if '# On-Point  Integ end' in line:          
            time_match = re.search(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})', line)
            if time_match:
                on_time_str = time_match.group(1)
                on_end_time = datetime.datetime.strptime(on_time_str, "%Y/%m/%d-%H:%M:%S.%f")

                # on_end_timeを追加する前に、その前に取得した値が正しいか確認。
                if 'on_end_time' in locals():  # on_end_time が定義されている場合にのみ追加
                    ret[f"on_end_time_{count}"] = on_end_time
                    ret[f"on_start_time_{count}"] = on_start_time
                    count += 1
    return ret


def extract_OnOfftime_from_ant30(ant30log):
    """
    abt30ログからOnOffTimeを読み取る。OFF点の観測開始と終了時間の取得に必要
    """
    OnOffTime = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            OnOffTime_match = re.search(r'OnOffTime\s+(\d+)', line)
            if OnOffTime_match:
                OnOffTime = OnOffTime_match.group(1)
                
    return OnOffTime    


def extract_OFF_time_from_ant30(ant30log, OnOffTime):
    """
    ant30logからON終了時刻off_end_timeをdatetimeに変換し、辞書に保存。
    OnOffTimeから、off_end_timeをもとにoff_start_timeを計算して、辞書に保存。
    """
    ret = {}

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    count = 1 

    for line in log_lines:
        if '# Off-Point Integ end' in line:          
            time_match = re.search(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})', line)

            if time_match:
                off_time_str = time_match.group(1)
                off_end_time = datetime.datetime.strptime(off_time_str, "%Y/%m/%d-%H:%M:%S.%f")
                off_start_time = off_end_time - datetime.timedelta(seconds=int(OnOffTime))

                ret[f"off_end_time_{count}"] = off_end_time
                ret[f"off_start_time_{count}"] = off_start_time

                count += 1

    return ret 


def calculate_average_OFFpower(ant30log, powerlog, off_dict):
    """
    各ON点ごとの観測開始(off_start_time)から終了(off_end_time)までの範囲のパワーメーター出力値を
    カウントごと取得し平均値を計算。辞書形式で保存。
    """ 
    average_OFF_power = {}

    power_dict = get_powerdata(powerlog)
    SetNumber = int(extract_SetNumber(ant30log))

    for count in range(1, SetNumber + 1): # SetNumberの回数分ループを作成
        start_key = f"off_start_time_{count}" 
        end_key = f"off_end_time_{count}"
        #print(f"calculate_average_OFFpower() Checking keys: {start_key}, {end_key}")

        if start_key not in off_dict or end_key not in off_dict:
            print(f"calculate_average_OFFpower() Key not found: {start_key} or {end_key}")
            continue

        # 各カウント数ごとの時刻範囲に含まれるパワーログの値を保存するためのリスト
        power_values = []  

        # 各タイムスタンプを個別に確認して、範囲内にあるかチェック
        for i, timestamp in enumerate(power_dict['date']):
            if off_dict[start_key] <= timestamp <= off_dict[end_key]:
                power_values.append(power_dict['power'][i])
                #print(f"calculate_average_OFFpower() Power value in range: {power_dict['power'][i]}")

        if power_values:
            average_OFF_power[f"average_OFF_power_{count}"] = np.mean(power_values)
        else:
            average_OFF_power[f"average_OFF_power_{count}"] = None

    return average_OFF_power


def extract_RSkyTime_from_ant30(ant30log):
    """
    R終了時間から逆算して求めるため、ant30ログからRskyTimeを読み取る。
    """
    RSkyTime = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            RSkyTime_match = re.search(r'RSkyTime\s+(\d+)', line)
            if RSkyTime_match:
                RSkyTime = int(RSkyTime_match.group(1))
                
    return RSkyTime    


def extract_Rtime_from_ant30(ant30log, RSkyTime):
    """
    ant30logを読み込み、R終了時の時刻情報をdatetimeに変換して辞書形式で保存。
    """
    ret = {}
    count = 1  # R終了時の時刻に順番をつけるためのカウンタ

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
        if '# R-Sky     Integ end' in line:   
                time_match = re.search(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})', line)
                if time_match:
                    R_time_str = time_match.group(1)
                    R_end_time = datetime.datetime.strptime(R_time_str, "%Y/%m/%d-%H:%M:%S.%f")
                    R_start_time = R_end_time - datetime.timedelta(seconds=int(RSkyTime))
                    ret[f"R_end_time_{count}"] = R_end_time
                    ret[f"R_start_time_{count}"] = R_start_time
                    count += 1

    return ret 


def calculate_average_Rpower(ant30log, powerlog, R_dict):
    """
    各Rごとの観測開始(R_start_time)から終了(R_end_time)までの範囲のパワーメーター出力値を
    カウントごとに取得し、平均値を計算して辞書に保存。
    """ 
    average_R_power = {}

    power_dict = get_powerdata(powerlog)
    SetNumber = int(extract_SetNumber(ant30log))

    for count in range(1, SetNumber + 1): # SetNumberの回数分ループを作成
        start_key = f"R_start_time_{count}" 
        end_key = f"R_end_time_{count}"
        #print(f"calculate_average_Rpower() Checking keys: {start_key}, {end_key}")

        if start_key not in R_dict or end_key not in R_dict:
            print(f"calculate_average_OFFpower() Key not found: {start_key} or {end_key}")
            continue

        # 各カウント数ごとの時刻範囲に含まれるパワーログの値を保存するためのリスト
        power_values = []  

        # 各タイムスタンプを個別に確認して、範囲内にあるかチェック
        for i, timestamp in enumerate(power_dict['date']):
            if R_dict[start_key] <= timestamp <= R_dict[end_key]:
                power_values.append(power_dict['power'][i])
                #print(f"calculate_average_Rpower() Power value in range: {power_dict['power'][i]}")

        if power_values:
            average_R_power[f"average_R_power_{count}"] = np.mean(power_values)
        else:
            average_R_power[f"average_R_power_{count}"] = None

    return average_R_power


def extract_SetNumber_from_ant30(ant30log):
    """
    ant30ログからSetNumberを読み取る。scan sequenceごとのプロットに必要。
    """
    SetNumber = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            SetNumber_match = re.search(r'SetNumber\s+(\d+)', line)

            if SetNumber_match:
                SetNumber = int(SetNumber_match.group(1))
                
    return SetNumber   


def extract_RSkyTime_from_ant30(ant30log):
    """
    R終了時間から逆算して求めるため、ant30ログからRskyTimeを読み取る。
    """
    RSkyTime = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            RSkyTime_match = re.search(r'RSkyTime\s+(\d+)', line)

            if RSkyTime_match:
                RSkyTime = int(RSkyTime_match.group(1))
                
    return RSkyTime    


def calculate_average_power_R(powerlog, R_start_time, R_end_time):
    """
    R観測の時刻範囲でパワーメーター出力値の平均値V_Rを戻り値として得る。
    """
    # パワーメーターログのフォーマット [yyyy/mm/dd-hh:mm:ss.ms] data
    powerlog_format = re.compile(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})\]\s+([\d\.]+)')

    power_values = []

    with open(powerlog, 'r') as file:
        lines = file.readlines()

        for line in lines:
            line = line.strip()

            match = powerlog_format.match(line)
            if match:
                timestamp_str = match.group(1)  # [yyyy/mm/dd-hh:mm:ss.ms]
                powerlog_time = datetime.datetime.strptime(timestamp_str, '%Y/%m/%d-%H:%M:%S.%f')
                power_value = float(match.group(2)) 

                if R_start_time <= powerlog_time <= R_end_time:
                    power_values.append(power_value)
                    #print(f"calculate_average_power_R() Added power value: {power_value} at {powerlog_time}")

    # 指定された範囲内にパワー値があれば平均を計算し、そうでなければNoneを返す
    if power_values:
        V_R = np.mean(power_values)
        return V_R
    else:
        print(f"No power values found within the range {R_start_time} to {R_end_time}")
        return None
    

def extract_OnOfftime_from_ant30(ant30log):
    """
    各OFF点ごとの観測開始時間を観測終了時間から逆算して求めるため、ant30ログからOnOffTimeを読み取る。
    """
    OnOffTime = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            OnOffTime_match = re.search(r'OnOffTime\s+(\d+)', line)

            if OnOffTime_match:
                OnOffTime = OnOffTime_match.group(1)
                
    return OnOffTime  


def calculate_average_power_ON(powerlog, off_start_time, off_end_time):
    """
    各OFF点ごとの観測開始(on_start_time)から終了(on_end_time)までの範囲のパワーメーター出力値を
    カウントごとに取得し、平均値を計算してリストに保存。
    """ 
    # パワーログのフォーマット（仮定） [yyyy/mm/dd-hh:mm:ss.ms] data
    powerlog_contents = re.compile(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})\]\s+([\d\.]+)')
    
    average_OFFpower_list = []

    with open(powerlog, 'r') as file:
        lines = file.readlines()

    for count in range(len(off_start_time)):
        start_time = off_start_time[count]  
        end_time = off_end_time[count]      

        # 指定されたカウントの範囲に含まれるパワー値を取得
        power_values = []
        for line in lines:
            match = powerlog_contents.match(line)
            if match:
                timestamp_str = match.group(1)  # [yyyy/mm/dd-hh:mm:ss.ms] タイムスタンプ部分を抽出
                powerlog_time = datetime.datetime.strptime(timestamp_str, '%Y/%m/%d-%H:%M:%S.%f')  # タイムスタンプをdatetimeに変換
                power_value = float(match.group(2))  # パワー値を数値として取得

                if start_time <= powerlog_time <= end_time:
                    power_values.append(power_value)

        if power_values:
            average_OFFpower = np.mean(power_values)
        else:
            average_OFFpower = None 

        average_OFFpower_list.append(average_OFFpower)

    return average_OFFpower_list

import os
def create_scanplot_dicts(ant30log, powerlog,T_atm, dict_azel, dict_power, on_dict, SetNumber):
    """
    各ON区間に対して、az, az_scanoffset, el, el_scanoffset, power をフィルタリングし、
    新しい辞書を作成する。
    dict_off_powerとdict_R_powerを使って、T_Bを計算する。

    SetNumberによって何セット分辞書に追加するか決める:
    SetNumber = 1 の場合、az_scan_1, el_scan_1
    SetNumber = 2 の場合、az_scan_1,2, el_scan_1,2
    SetNumber = 3 の場合、az_scan_1,2,3, el_scan_1,2,3

    プロットの結果をテキストファイルに保存する。
    """
    ret = {}

    # 各セットごとのOFF点観測時の平均出力を計算（T_B計算用）
    OnOffTime = extract_OnOfftime_from_ant30(ant30log)  # ant30ログからOnOffTImeを取得
    off_dict = extract_OFF_time_from_ant30(ant30log, OnOffTime)  # ant30ログからOFF点観測時間を取得
    dict_off_power = calculate_average_OFFpower(ant30log, powerlog, off_dict)  # OFF点観測時の平均出力を計算

    # 各セットごとのR観測時の平均出力を計算（T_B計算用）
    RSkyTime = extract_RSkyTime_from_ant30(ant30log)
    R_dict = extract_Rtime_from_ant30(ant30log, RSkyTime)
    dict_R_power = calculate_average_Rpower(ant30log, powerlog, R_dict)

    # プロット結果を保存するディレクトリを作成
    ret = get_azel_scanoffset_ant30log(ant30log)
    directory = ret['fn'] + '_plot'
    if not os.path.exists(directory):
        os.makedirs(directory)

    for count in range(1, SetNumber + 1):
        az_idx = 2 * count - 1  # 奇数インデックス (1, 3, 5...)
        el_idx = 2 * count      # 偶数インデックス (2, 4, 6...)

        # AZ_scanoffset 
        az_filter = np.where(np.logical_and(on_dict[f"on_start_time_{az_idx}"] <= dict_azel['date'],
                                            dict_azel['date'] <= on_dict[f"on_end_time_{az_idx}"]))
        az_scanoffset = dict_azel["AZ_scanoffset"][az_filter].tolist()
        az_real = dict_azel["AZ"][az_filter].tolist()
        el_real = dict_azel["EL"][az_filter].tolist()
        az_power_data = np.array(dict_power["power"][az_filter])
        
        # T_Bの計算
        off_power = dict_off_power[f"average_OFF_power_{count}"]
        R_power = dict_R_power[f"average_R_power_{count}"]
        T_B_az = T_atm * (az_power_data - off_power) / (R_power - off_power)

        ret[f"az_scan_{count}"] = {
            "AZ": az_real, "EL": el_real, "AZ_scanoffset": az_scanoffset, 
            "power_az": az_power_data, f"T_B_az_{count}": T_B_az.tolist()
        }

        # EL_scanoffset
        el_filter = np.where(np.logical_and(on_dict[f"on_start_time_{el_idx}"] <= dict_azel['date'],
                                            dict_azel['date'] <= on_dict[f"on_end_time_{el_idx}"]))
        el_scanoffset = dict_azel["EL_scanoffset"][el_filter].tolist()
        az_real = dict_azel["AZ"][el_filter].tolist()
        el_real = dict_azel["EL"][el_filter].tolist()
        el_power_data = dict_power["power"][el_filter].tolist()

        # T_B の計算
        T_B_el = T_atm * (np.array(el_power_data) - off_power) / (R_power - off_power)
        ret[f"el_scan_{count}"] = {
            "AZ": az_real, "EL": el_real, "EL_scanoffset": el_scanoffset, 
            "power_el": el_power_data, f"T_B_el_{count}": T_B_el.tolist()
        }

        # AZスキャンデータを保存
        az_filename = os.path.join(directory, f"az_scanplot_{az_idx}.txt")
        with open(az_filename, "w") as f:
            f.write("AZ [deg], EL [deg], AZ_scanoffset [arcsec], power [dBm], T_B [K]\n")
            output_data_az = np.column_stack([ret[f"az_scan_{count}"]["AZ"], 
                                              ret[f"az_scan_{count}"]["EL"], 
                                              ret[f"az_scan_{count}"]["AZ_scanoffset"], 
                                              ret[f"az_scan_{count}"]["power_az"], 
                                              ret[f"az_scan_{count}"][f"T_B_az_{count}"]])
            for row in output_data_az:
                f.write(f"{row[0]:.6f},{row[1]:.6f},{row[2]:.6f},{row[3]:.6f},{row[4]:.6f}\n")

        # ELスキャンデータを保存
        el_filename = os.path.join(directory, f"el_scanplot_{el_idx}.txt")
        with open(el_filename, "w") as f:
            f.write("AZ [deg], EL [deg], EL_scanoffset [arcsec], power [dBm], T_B [K]\n")
            output_data_el = np.column_stack([ret[f"el_scan_{count}"]["AZ"],
                                              ret[f"el_scan_{count}"]["EL"], 
                                              ret[f"el_scan_{count}"]["EL_scanoffset"], 
                                              ret[f"el_scan_{count}"]["power_el"], 
                                              ret[f"el_scan_{count}"][f"T_B_el_{count}"]])
            for row in output_data_el:
                f.write(f"{row[0]:.6f},{row[1]:.6f},{row[2]:.6f},{row[3]:.6f},{row[4]:.6f}\n")

    return ret


mpl.rcParams.update({'font.size': 10})
mpl.rcParams.update({'axes.grid': True})
mpl.rcParams.update({'grid.linestyle': ':'})

# インタラクティブ動作 
# グローバル変数
lines = []  # 各プロットごとの水平線を保持
selected_line = None  # 現在選択中の線
selected_idx = None  # 現在選択中のプロットのインデックス
y_positions = {}  # 各プロットごとの線の位置を保持
ax = None  # グローバルでプロットの軸を管理
temp_file = "threshold.tmp"  # 一時ファイル

def save_thresholds_to_temp():
    """赤線の位置を一時ファイルに保存"""
    with open(temp_file, "w") as f:
        for idx, y in y_positions.items():
            f.write(f"{y:.2f}\n")
    print(f"Thresholds saved to temp file: {temp_file}")

def update_legend(axis, idx):
    """個別のプロットに凡例を更新"""
    axis.legend(
        handles=[
            plt.Line2D([], [], color='red', linestyle='-', linewidth=2, label=f"Threshold: {y_positions[idx]:.2f}"),
        ],
        loc="upper right"
    )


def on_click(event):
    """クリックで線を選択または固定"""
    global selected_line, selected_idx
    if event.ydata is None or event.inaxes is None:  # プロット外なら無視
        return

    # 対象プロットの軸を特定
    for idx, axis in enumerate(ax):
        if event.inaxes == axis:
            if selected_line is None:  # 線が未選択の場合
                # 選択対象の線を探す
                for line in lines[idx]:
                    if abs(event.ydata - line.get_ydata()[0]) < 5.0:  # 線に近いか判定
                        selected_line = line
                        selected_idx = idx
                        return
            else:  # 線が既に選択中の場合
                selected_line = None
                selected_idx = None
                return


def motion(event):
    """マウス移動で選択中の線を動かす"""
    global selected_line, selected_idx
    if event.ydata is None or selected_line is None or selected_idx is None:  # プロット外または未選択なら無視
        return

    # 選択中の線の位置を更新
    selected_line.set_ydata([event.ydata])
    # グローバルの y_positions を更新
    y_positions[selected_idx] = event.ydata

    # 即座に凡例を更新して再描画
    update_legend(ax[selected_idx], selected_idx)  # 対応するプロットの凡例を更新
    ax[selected_idx].figure.canvas.draw_idle()  # 最小限の再描画

    save_thresholds_to_temp() # 閾値をtemoファイルに保存


def plot_azel_scans(ant30log, plot_dict, SetNumber):
    """AZELスキャンのプロットを作成し、インタラクティブな線を追加"""
    global ax, y_positions, lines
    fig, ax = plt.subplots(SetNumber, 2, figsize=(10, 5 * SetNumber))
    ax = ax.flatten()  # ループで扱いやすくするために1次元化

    # 初期化
    lines = [[] for _ in range(len(ax))]
    y_positions = {i: 10 for i in range(len(ax))}  # 各プロットに初期値を設定

    for i in range(SetNumber):
        # AZ_scan plot
        az_idx = 2 * i
        ax[az_idx].plot(
            plot_dict[f"az_scan_{i+1}"]["AZ_scanoffset"],
            plot_dict[f"az_scan_{i+1}"][f"T_B_az_{i+1}"]
        )
        ax[az_idx].set_xlabel("AZ Scan Offset [arcsec]")
        ax[az_idx].set_ylabel(r"$T_B$ [K]")
        ax[az_idx].set_title(f"AZ_scan, {i+1} set")
        line = ax[az_idx].axhline(y_positions[az_idx], color='red', linestyle='-', linewidth=2)
        lines[az_idx].append(line)  # プロットごとの線をリストに追加
        update_legend(ax[az_idx], az_idx)

        # EL_scan plot
        el_idx = 2 * i + 1
        ax[el_idx].plot(
            plot_dict[f"el_scan_{i+1}"]["EL_scanoffset"],
            plot_dict[f"el_scan_{i+1}"][f"T_B_el_{i+1}"]
        )
        ax[el_idx].set_xlabel("EL Scan Offset [arcsec]")
        ax[el_idx].set_ylabel(r"$T_B$ [K]")
        ax[el_idx].set_title(f"EL_scan, {i+1} set")
        line = ax[el_idx].axhline(y_positions[el_idx], color='red', linestyle='-', linewidth=2)
        lines[el_idx].append(line)  # プロットごとの線をリストに追加
        update_legend(ax[el_idx], el_idx)

    # プロット間の余白を調整
    fig.subplots_adjust(top=0.95, hspace=0.5, wspace=0.3)

    # インタラクティブ機能を登録
    fig.canvas.mpl_connect('button_press_event', on_click)
    fig.canvas.mpl_connect('motion_notify_event', motion)

    # プロットを保存
    ret = get_azel_scanoffset_ant30log(ant30log)
    directory = ret['fn'] + '_plot'
    os.makedirs(directory, exist_ok=True)
    #plt.savefig(os.path.join(directory, ret['fn'] + '_plot.png'))
    plt.show()


def main(ant30log, powerlog):
    """
    プロット
    T_ambをキーボード入力し、縦軸T_Bとして表示させる。
    """
    dict_azel = get_azel_scanoffset_ant30log(ant30log) # ant30ログからaz_scanoffset, el_scanpffset, timestampを取得
    dict_power = get_powerdata(powerlog) # パワメーターログからpower, timestampを取得

    SetNumber = SetNumber = int(extract_SetNumber(ant30log)) # ant30ログから何セット観測したかを取得。プロット、T_B計算で分岐処理に使用
    
    # 横軸scanoffset, 縦軸T_B のプロット
    T_amb = float(input("キャリブレーターの温度 T_amb [K] を入力: "))
    on_dict = extract_ON_time_from_ant30(ant30log) # 縦軸のT_B計算用 
    plot_dict = create_scanplot_dicts(ant30log, powerlog, T_amb, dict_azel, dict_power, on_dict, SetNumber)
    plot_azel_scans(ant30log, plot_dict, SetNumber)
     

# ターミナルからコマンドを打ち込んで実行
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('ant30log', help='ant30 logfile name')
    parser.add_argument('powerlog', help='powermeter logfile name')
    #parser.add_argument('output_filename', help='Output file name of calculation results')
    
    args = parser.parse_args()
    main(args.ant30log,args.powerlog)

#ant30log = "ant30-2degrpsn-20240927161948.log"
#powerlog = "power-2024092716.log"
