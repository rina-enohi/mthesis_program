#!python3

import numpy as np
import datetime
import re
import datetime
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

"""
2024/11/28
出力プロットのファイル名をant30ログ名+pngとした。
凡例の表示を変更。
"""


def extract_el_ON_from_ant30(ant30log):
    """
    ant30logを読み込み、各ON点ごとのELを数値としてリストに保存。
    """
    on_el_list = []

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:

        if '# On-Point  Integ end' in line:
            count_match = re.search(r'On-Count:(\d+)', line)

            if count_match:
                el_match = re.search(r'\(AZ,EL\) = \([\d\.\-]+, ([\d\.\-]+)\)', line)

                if el_match:
                    el_value = float(el_match.group(1))
                    on_el_list.append(el_value)

    return on_el_list



def extract_OnOfftime_from_ant30(ant30log):
    """
    各ON点ごとの観測開始時間を観測終了時間から逆算して求めるため、ant30ログからOnOffTimeを読み取る。
    """
    OnOffTime = None

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:
            OnOffTime_match = re.search(r'OnOffTime\s+(\d+)', line)

            if OnOffTime_match:
                OnOffTime = OnOffTime_match.group(1)
                
    return OnOffTime    



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



def extract_R_time_from_ant30(ant30log, RSkyTime):
    """
    ant30logからR終了時刻R_end_timeをdatetimeに変換。
    RSkyTimeから、R_end_timeをもとにR_start_timeを計算する。
    """

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:

        if '# R-Sky     Integ end' in line:                
                time_match = re.search(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})', line)

                if time_match:
                    R_time_str = time_match.group(1)
                    R_end_time = datetime.datetime.strptime(R_time_str, "%Y/%m/%d-%H:%M:%S.%f")
                    R_start_time = R_end_time - datetime.timedelta(seconds=int(RSkyTime))  

    return R_end_time, R_start_time



def extract_ON_time_from_ant30(ant30log, OnOffTime):
    """
    ant30logからON終了時刻on_end_timeをdatetimeに変換し、リストに保存。
    OnOffTimeから、on_end_timeをもとにon_start_timeを計算して、リストに保存。
    """
    #RSkyTime = extract_RSkyTime_from_ant30(ant30log)
    on_end_time_list = []
    on_start_time_list = []

    with open(ant30log, 'r', encoding='utf-8') as file:
        log_lines = file.readlines()

    for line in log_lines:

        if '# On-Point  Integ end' in line:          
                time_match = re.search(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})', line)

                if time_match:
                    on_time_str = time_match.group(1)
                    on_end_time = datetime.datetime.strptime(on_time_str, "%Y/%m/%d-%H:%M:%S.%f")
                    on_end_time_list.append(on_end_time)

                    on_start_time = on_end_time - datetime.timedelta(seconds=int(OnOffTime))  
                    on_start_time_list.append(on_start_time)

    return on_end_time_list, on_start_time_list



def calculate_average_power_ON(powerlog, on_start_time, on_end_time):
    """
    各ON点ごとの観測開始(on_start_time)から終了(on_end_time)までの範囲のパワーメーター出力値を
    カウントごとに取得し、平均値を計算してリストに保存。
    """ 
    # パワーログのフォーマット（仮定） [yyyy/mm/dd-hh:mm:ss.ms] data
    powerlog_contents = re.compile(r'\[(\d{4}/\d{2}/\d{2}-\d{2}:\d{2}:\d{2}\.\d{3})\]\s+([\d\.]+)')
    
    average_ONpower_list = []

    with open(powerlog, 'r') as file:
        lines = file.readlines()

    for count in range(len(on_start_time)):
        start_time = on_start_time[count]  
        end_time = on_end_time[count]      

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
            average_ONpower = np.mean(power_values)
        else:
            average_ONpower = None 

        average_ONpower_list.append(average_ONpower)

    return average_ONpower_list



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
                    #print(f"Added power value: {power_value} at {powerlog_time}")

    # 指定された範囲内にパワー値があれば平均を計算し、そうでなければNoneを返す
    if power_values:
        V_R = np.mean(power_values)
        return V_R
    else:
        print(f"No power values found within the range {R_start_time} to {R_end_time}")
        return None


def main(ant30log, powerlog):
    """
　　 縦軸にln[ (V(R) - V(Z)) / V(R) ]、横軸にsecZ をとり最小二乗法で線形フィッティング
　　 傾きから光学的厚み：τ0、切片からTsys, Trxを求める。ただしT_atmはキーボード入力する
    """

    # 各ON点ごとのパワーメーター出力の平均値を計算しリストに保存
    OnOffTime = extract_OnOfftime_from_ant30(ant30log)
    on_end_time, on_start_time = extract_ON_time_from_ant30(ant30log, OnOffTime)
    average_ONpower= calculate_average_power_ON(powerlog, on_start_time, on_end_time)
    average_ONpower = np.array(average_ONpower)

    # 各ON点観測時のELをリストをNumPy配列に変換
    on_el = extract_el_ON_from_ant30(ant30log)
    on_el = np.array(on_el)

    secZ = 1 / np.cos(np.radians(90 - on_el)) 

    output_data = np.column_stack((on_el, secZ, average_ONpower))
    
    output_filename = ant30log.replace('.log', '.txt')
    with open(output_filename, 'w') as f:
        f.write('EL,secZ,power\n')
        for row in output_data:
            try:
                f.write(f'{row[0]:.6f},{row[1]:.6f},{row[2]:.6f}\n') 
            except ValueError as e:
              print(f"Error converting row {row}: {e}")
            
    secZ = output_data[:, 1]
    power = output_data[:, 2]

    # R時のパワーメーター出力の平均値を計算
    RSkyTime = extract_RSkyTime_from_ant30(ant30log)
    R_end_time, R_start_time = extract_R_time_from_ant30(ant30log, RSkyTime)
    V_R = calculate_average_power_R(powerlog, R_start_time, R_end_time)
    V_R = float(V_R)
   
    y = np.log( (V_R - power) / V_R ) 
        
    a, b = np.polyfit(secZ, y, 1)

    T_atm = float(input("大気の温度 T_atm [K] を入力: "))
    T_rx =  (np.exp(-b) - 1) * T_atm 
    T_sys = (np.exp( -(a+b)) - 1) * T_atm

    # 符号を条件付きで表示
    b_sign = "+" if b >= 0 else "-"
    b_abs = abs(b)  # 絶対値を取る

    print(f"最小二乗フィッティング: y = {a:.3f} secZ {b_sign} {b_abs:.3f}")
    #print(f"最小二乗フィッティング: y = {a:.3f} secZ + {b:.3f}")
    print(f'天頂方向の光学的厚み tau_0 = {-a:.3f}')
    print(f'T_atm = {T_atm:.3f} K')
    print(f'T_rx = {T_rx:.3f} K')
    print(f'T_sys = {T_sys:.3f} K')

    # τをconfに書き込む
    #modify_tau_value('../etc/ant30_phaseC0.conf',a)

    mpl.rcParams.update({'font.size': 14})
    mpl.rcParams.update({'axes.facecolor': 'w'})
    mpl.rcParams.update({'axes.edgecolor': 'k'})
    mpl.rcParams.update({'figure.facecolor': 'w'})
    mpl.rcParams.update({'figure.edgecolor': 'w'})
    mpl.rcParams.update({'axes.grid': True})
    mpl.rcParams.update({'grid.linestyle': ':'})
    mpl.rcParams.update({'figure.figsize': [8, 6]})

    plt.scatter(secZ, y, label='data') 
    plt.plot(secZ, a * secZ + b, color='red', label=f' y = {a:.3f} x {b_sign} {b_abs:.3f}') 
    plt.xlabel('secZ')
    plt.ylabel(r'$ln[\frac{V_{R}-V(Z)}{V_{R}}]$')
    plt.title(f"Linear Fit: y = {a:.3f} secZ {b_sign} {b_abs:.3f}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(ant30log.replace('.log', '.png'))
    plt.show()


def modify_tau_value(filename, TAU):
    """
     ../etc/ant30_phaseC0.confの値を自動で書き換える
    """
  
    with open(filename, 'r') as file:
        lines = file.readlines()

    found_tau_keyword = False
    modified_lines = []

    for line in lines:
        if '#Optical depth tau' in line:
            found_tau_keyword = True 
        elif found_tau_keyword and 'TAU' in line:
            parts = line.split()
            if len(parts) == 2 and parts[0] == 'TAU':
                line = f"{parts[0]}            {TAU}\n"
            found_tau_keyword = False 
        modified_lines.append(line)

    with open(filename, 'w') as file:
        file.writelines(modified_lines)


# ターミナルからコマンドを打ち込んで実行
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('ant30log', help='ant30 logfile name')
    parser.add_argument('powerlog', help='powermeter logfile name')
    
    args = parser.parse_args()
    main(args.ant30log,args.powerlog)

#ant30log = 'ant30-tau1-202409025.log'
#powerlog = 'power-202409025.log'
