# 简介
7ma出行app，免费骑车

# 原理
利用7ma出行app下单开锁后，两分钟之内立即还车不收费，实现白嫖用车，总共两个python脚本，利用flask框架构建

app.py 实现下单开锁的功能

scheduler.py 实现监听订单状态，每一分钟检查一次，发现订单立即还车

提示：钱包里至少要留一分钱，才能下单

# IOS 7ma出行 扫码版
iOS用户可以直接使用下面这个快捷指令，注释在第一行，自行查看
```
https://www.icloud.com/shortcuts/528ae1ae4f8e4b60a1b15859f2c167eb
```

# 抓包
首先要抓包newmapi.7mate.cn这个域名下，请求头里面的Authorization，大概形式是这样
```
Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpcxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
复制保存好，后面的部署需要将这段Authorization填入到Authorization.txt里面

# web部署
<details>
  <summary>方式一、docker运行</summary>

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
然后去 /root/7ma/config 目录
```
cd /root/7ma/config
```
创建Authorization.txt，填写好自己的Authorization后，esa 接着输入 :wq 保存退出
```
vi Authorization.txt
```

### 3.启动docker
首先进入 /root/7ma
```
cd /root/7ma
```
然后创建并启动docker
```
docker run -dit --name 7ma \
  --hostname 7ma \
  --restart always \
  -p 4321:4321 \
  -v $PWD/config:/app/config \
  -v $PWD/logs:/app/logs \
  zhacha222/7ma:latest
```
### 4.访问网站
```
IP:4321
```
</details>


<details>
  <summary>方式二、vps部署</summary>

### 1.使用wget下载源码
```
wget https://github.com/zhacha222/7ma/releases/download/v1.0/7ma_web.v1.0.zip -P /root
```
### 2.解压源码（假设你已经安装了unzip）
```
unzip /root/aaaa/7ma_web.v1.0.zip -d /root
```
### 3.删除压缩包
```
rm /root/7ma_web.v1.0.zip
```
### 4.在/root/7ma/config文件夹创建Authorization.txt，填写好自己的Authorization
### 5.安装python3.7.5
### 6.安装依赖
```
pip3 install Flask requests
```
### 7.启动
```
python3 app.py
```
### 8.访问网站
```
IP:4321
```
</details>

<details>
  <summary>方式三、宝塔部署</summary>

### 1.下载最新源码（在[releases](https://github.com/zhacha222/7ma/releases/tag/v1.0)里面）
### 2.解压到 /root路径下
### 3.侧边栏打开网站—python项目
### 4.添加python项目
### 5.配置参数
```
启动文件选择app.py
python版本选择3.7.5
运行方式选择python
其他自己填
```
### 6.确认
### 7.访问网站
```
http://localhost:4321
```
</details>


<details>
  <summary>方式四、本地python运行(本地调试环境python3.7.5)</summary>

### 1.下载最新源码（在[releases](https://github.com/zhacha222/7ma/releases/tag/v1.0)里面）
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
</details>


# 7ma出行 API 文档
<details>
  <summary>获取首页</summary>


  - **请求方法：** GET
  - **URL：** http://IP:4321/
  - **描述：** 获取7ma出行App首页。
</details>

<details>
  <summary>提交订单</summary>

  - **请求方法：** POST
  - **URL：** http://IP:4321/process
  - **描述：** 提交订单并尝试开锁。
  - **请求体：**
    - **bike_number (string, 必需)：** 要租借的车辆编号。
</details>

<details>
  <summary>示例请求：</summary>

  ```http
  POST /process
  Content-Type: application/json

  {
    "bike_number": "123456"
  }
  ```
</details>

<details>
  <summary>示例响应：</summary>


  成功响应：

  ```json
  {
    "message": "下单成功",
    "unlock_result": "开锁成功",
    "is_success": true
  }
  ```

  失败响应：

  ```json
  {
    "message": "下单失败，请稍后再试。",
    "is_success": false
  }
  ```
</details>

<details>
  <summary>注意事项：</summary> 

  - 一分钟内只能提交一次订单，否则会收到 "一分钟内只能提交一次订单，请稍后再试。" 的错误响应。
  - 如果订单成功，将尝试开锁，如果开锁成功，将返回 "开锁成功" 的响应。

</details>

