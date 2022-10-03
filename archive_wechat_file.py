import os
import time
import shutil
import hashlib
import datetime
import filecmp


def TimeStampToTime(timestamp):
    timeStruct = time.localtime(timestamp)
    return time.strftime('%Y-%m', timeStruct)


def get_change_time(file_path):
    chuangjian = TimeStampToTime(os.stat(file_path).st_ctime)
    # print(chuangjian)  # 文件的添加时间
    return chuangjian


def return_md5(file):
    md5file = open(file, 'rb')
    md5 = hashlib.md5(md5file.read()).hexdigest()
    md5file.close()
    return md5


def mkdir_target(riqi):
    # 目标文件
    path = ''
    try:
        os.mkdir(path + str(riqi))
    except:
        pass


def return_target_file_name(target_path):
    # 返回的不带路径
    a = []
    g = os.walk(target_path)
    for path, dir_list, file_list in g:
        for file_list in file_list:
            a.append(file_list)
    return a


def scanning_file(source_path2):
    # source 是 mac 微信的路径
    # targee 是 目标 的路径
    # 要检查的文件夹
    g = os.walk(source_path2)
    for path, dir_list, source_file_list in g:
        # 第一个循环，遍历所有source文件
        for source_file_list in source_file_list:
            # 第二个循环，遍历所有souce文件名字
            riqi = get_change_time(str(path) + '/' + str(source_file_list))
            target_path = '' + riqi
            target_path_file_name = return_target_file_name(target_path)
            # 获取目标文件夹内的文件名

            # 防止找不到riqi文件而直接跳过for导致报错
            status = 3

            for i in target_path_file_name:
                if i == source_file_list:
                    md5_target = return_md5(target_path + '/' + i)
                    md5_source = return_md5(path + '/' + source_file_list)

                    if md5_target == md5_source:
                        status = 2
                        break
                    else:
                        # 重新查md5
                        print(i)
                        target_path_file_name.remove(i)
                        for uu in target_path_file_name:
                            md5_target = return_md5(target_path + '/' + uu)
                            md5_source = return_md5(path + '/' + source_file_list)
                            if uu == target_path_file_name:
                                status = 1
                                break
                            else:
                                status = 2
                        break

                else:
                    status = 3
            # status ==
            # 1: 名字一样，md5不一样，重命名复制
            # 2：名字一样，md5一样，跳过  or 名字不一样，md5一样，跳过
            # 3：名字不一样，直接复制

            if status == 3:
                # 名字不一样
                mkdir_target(riqi)
                target_path = '' + riqi
                # print(path)
                try:
                    shutil.copy2(str(path) + '/' + str(source_file_list), target_path)
                except:
                    print(source_file_list)
                print('复制了：', source_file_list)

            elif status == 1:
                # 如果md5不一样而且名字一样
                # file_list应该改名
                num = source_file_list.find('.')
                shijian = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())

                # 迁移到中转站
                # z中转站路径
                transit_path = ''


                shutil.copy2(str(path) + '/' + str(source_file_list), transit_path + source_file_list)

                # 在中转处重命名
                file_list2 = transit_path + '/' + source_file_list[:num] + '_' + str(shijian) + source_file_list[
                                                                                                num:]
                file_name = source_file_list[:num] + '_' + str(shijian) + source_file_list[num:]
                os.rename(str(transit_path) + '/' + source_file_list, file_list2)

                # 复制重命名后到目标目录
                mkdir_target(riqi)
                try:
                    shutil.copy2(str(transit_path) + '/' + str(file_name), target_path)
                except:
                    print(file_name)
                print('重命名了：', file_name, md5_target, md5_source)
            else:
                print('跳过了', source_file_list)
                pass


def get_wx_file_path():
    # 要检查的文件夹，注意替换
    g = os.walk(
        '/Users/#你的用户名#/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/**/**/Message/MessageTemp')
    a = []
    for path, dir_list, file_list in g:
        if path.find('File') != -1 or path.find('OpenData') != -1:
            a.append(path)
    return a


while 1:
    work_path = get_wx_file_path()
    for i in range(len(work_path)):
        scanning_file(work_path[i])
    time.sleep(200)
