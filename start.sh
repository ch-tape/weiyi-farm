#!/bin/bash
cd ~/Desktop/伟一农场
# 删除旧数据库重新开始
rm -f farm.db
echo "🚀 启动伟一农场服务..."
python3 server.py &
SERVER_PID=$!
sleep 1
# 测试
echo "--- 注册测试用户 ---"
curl -s -X POST http://localhost:6789/api/register -H 'Content-Type: application/json' -d '{"username":"张三","password":"123456"}'
echo ""
curl -s -X POST http://localhost:6789/api/register -H 'Content-Type: application/json' -d '{"username":"李四","password":"123456"}'
echo ""
curl -s -X POST http://localhost:6789/api/register -H 'Content-Type: application/json' -d '{"username":"王五","password":"123456"}'
echo ""
echo "--- 排行榜 ---"
curl -s http://localhost:6789/api/rank
echo ""
echo ""
echo "✅ 游戏已启动！"
echo "📱 浏览器打开: http://localhost:6789"
echo "🌐 局域网点此: http://$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1 | head -1 | awk '{print $2}'):6789"
echo ""
echo "服务器 PID: $SERVER_PID"
echo "停止服务: kill $SERVER_PID"
wait
