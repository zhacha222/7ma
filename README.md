# 7ma
7ma出行app，免费骑车


# 部署
## 一、docker一键部署
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
然后去 /root/7ma/config 目录创建Authorization.txt，填写自己的Authorization

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

## 二、python运行
