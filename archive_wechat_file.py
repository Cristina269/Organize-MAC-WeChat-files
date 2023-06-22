import os
import time
import shutil
import hashlib
import datetime
import filecmp

root_dir=(
    ''  # 微信文件所在的路径，不用加/
)

transit_path = '' # 中转站的路径，最后要加上/
target_path2 = '' # 用于存储复制过来的文件的目标目录，最后要加上/

def TimeStampToTime(timestamp):
    timeStruct = time.localtime(timestamp)
    return time.strftime('%Y-%m', timeStruct)


def get_change_time(file_path):
    creation_time = TimeStampToTime(os.stat(file_path).st_ctime)
    return creation_time


def return_md5(file):
    md5file = open(file, 'rb')
    md5 = hashlib.md5(md5file.read()).hexdigest()
    md5file.close()
    return md5


def mkdir_target(riqi):
    path = target_path2  # 目标文件
    try:
        os.mkdir(path + str(riqi))
    except:
        pass


def return_target_file_name(target_path):
    # Returns filenames without the path
    filenames = []
    for path, dir_list, file_list in os.walk(target_path):
        for file_name in file_list:
            filenames.append(file_name)
    return filenames


def scanning_file(source_path2):
    """
    source 是 mac 微信的路径
    targee 是 目标 的路径
    要检查的文件夹
    """
    file_tree = os.walk(source_path2)
    for path, dir_list, source_file_list in file_tree:  # 第一个循环，遍历所有source文件
        for source_file_list in source_file_list:  # 第二个循环，遍历所有souce文件名字

            # 防止找不到riqi文件而直接跳过for导致报错
            riqi = get_change_time(str(path) + '/' + str(source_file_list))
            target_path = target_path2 + riqi
            target_path_file_name = return_target_file_name(target_path)  # 获取目标文件夹内的文件名

            status = 3
            for i in target_path_file_name:
                # 文件名相同
                if i == source_file_list:
                    md5_target = return_md5(target_path + '/' + i)
                    md5_source = return_md5(path + '/' + source_file_list)

                    # MD5相同（两个重名的文件
                    if md5_target == md5_source:
                        status = 2
                        break

                    # MD5不同（两个重名的文件
                    else:
                        status = 1
                        break

                else:
                    status = 3
            print(status)

            """
            status
            1: 名字一样，md5不一样，重命名复制
            2：名字一样，md5一样，跳过
            3：名字不一样，直接复制
            """
            if status == 3:

                mkdir_target(riqi)
                target_path = target_path2 + riqi
                try:
                    shutil.copy2(str(path) + '/' + str(source_file_list), target_path)
                except:
                    print(source_file_list)
                print('复制了：', source_file_list,target_path)

            elif status == 1:
                # 如果md5不一样而且名字一样
                # file_list应该改名
                num = source_file_list.find('.')
                shijian = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())

                # 迁移到中转站
                # 中转站路径
                shutil.copy2(str(path) + '/' + str(source_file_list), transit_path + source_file_list)

                # 在中转处重命名
                file_list2 = transit_path + '/' + source_file_list[:num] + '_' + str(shijian) + source_file_list[
                                                                                                num:]
                file_name = source_file_list[:num] + '_' + str(shijian) + source_file_list[num:]
                os.rename(str(transit_path) + '/' + source_file_list, file_list2)

                # 复制重命名后到目标目录
                mkdir_target(riqi)
                try:
                    shutil.move(str(transit_path) + '/' + str(file_name), target_path)
                except:
                    print(file_name)
                print('重命名了：', file_name, md5_target, md5_source)
            else:
                print('跳过了', source_file_list)
                pass


def get_wechat_file_paths():
    # 定义要扫描的目录，替换成你实际的目录

    wechat_paths = []
    for current_path, directories, files in os.walk(root_dir):
        if 'File' in current_path or 'OpenData' in current_path:
            wechat_paths.append(current_path)
    return wechat_paths


while 1:
    work_path = get_wechat_file_paths()
    print(work_path)
    for i in range(len(work_path)):
        scanning_file(work_path[i])
    break
