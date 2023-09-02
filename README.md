# 简介
7ma出行app，免费骑车

# 原理
利用7ma出行app下单开锁后，两分钟之内立即还车不收费，实现白嫖用车

app.py实现下单开锁的功能

scheduler.py实现监听订单状态，每一分钟检查一次，发现订单立即还车

# IOS
### 7ma出行 扫码版
iOS用户可以直接使用下面这个快捷指令，注释在第一行，自行查看
```
https://www.icloud.com/shortcuts/528ae1ae4f8e4b60a1b15859f2c167eb
```

# web部署
## 方式一、docker一键部署
### 1.创建映射日志目录
```
mkdir /root/7ma
mkdir /root/7ma/logs
```

### 2.创建config文件夹并填写Authorization.txt
首先创建config文件夹
```
mkdir /root/7ma/config
```
然后去 /root/7ma/config 目录创建Authorization.txt，填写好自己的Authorization

### 3.启动docker

```
docker run -dit --name 7ma \
  --hostname 7ma \
  --restart always \
  -p 4321:4321 \
  -v $PWD/config:/app/config \
  -v $PWD/logs:/app/logs \
  zhacha222/7ma:latest
```

# 方式二、vps部署
### 1.把源码下载然后上传进vps
### 2.在config文件夹创建Authorization.txt，填写好自己的Authorization
### 3.安装python3.7.5
### 4.安装依赖
```
pip3 install Flask requests
```
### 5.启动
```
python3 app.py
```
### 6.访问网站
```
IP:4321
```

# 方式三、宝塔部署


## 方式四、本地python运行(本地调试环境python3.7.5)
### 1.把源码下载下来
### 2.在config文件夹创建Authorization.txt，填写好自己的Authorization
### 3.安装依赖
```
pip3 install Flask requests
```
### 4.启动
```
python3 app.py
```
### 5.访问网站
```
http://localhost:4321
```

