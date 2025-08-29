# 游戏关卡

### 比赛任务 (Missions)

开发一个 AI Agent，接收用户输入的自然语言指令，在 20 个关卡（暂定）中完成任务目标。每当完成一个关卡，游戏将生成一份加密日志，参赛者需上传该日志至官网用于评分，得分将实时公布在 [Leader boards]() 榜单。


### Log文件
  
完成  

MacOS位于 ： ~/Library/Application Support/OpenRA/Logs  
Windows位于：%APPDATA%\OpenRA\Logs

### 关卡场景

游戏关卡设计的难度有易有难，涵盖多种挑战。不同的关卡反映不同的场景：

部分关卡存在限时，超时会扣除50分

- Mission-01 Basic Building  
  - 基础建造
  - Score：100  
- Mission-02 Fog of War
  - 探索地图，达到80%探索度
  - Score：115 - 耗时(second)  
- Mission-03 Advanced Building
  - 建造更多建筑和单位
  - Score: 100
- Mission-04 Air Strike
  - 用Yaks摧毁敌方基地
  - Score: 220 - 5 * lossYaks - 耗时(second)  
- Mission-05 Basic Defense
  - 基础防御
  - Score: 10 + 2 * KilledEnemy  + 50(killedAllEnemy)
- Mission-06 Unit Counter
  - 兵种克制
  - Score: 100 - 10 * LossTank - 5 * LossInfantry
- Mission-07 Advanced Attack
  - 全面进攻，注意前后站位哦
  - Score: 50(DestoryEnemyBase) + 10 * DestoryEnemyPower + 1 * DestoryEnemyUnit - 2 * LossUnit
- Mission-08 Resource Management  
  - 在建造的过程中管理资源，保证在建造的过程中不会出现资源短缺（资源数量<=0）
  - Score: 100 + 10 (NoResourceShortage) + 10 (NoPowerShortage)
- Mission-09 Attack on Allies
  - 你带领了你的小队前往了前线，守护你的阵地（保护空军基地）（查询指令中，空军基地为：fcom）
  - 到达某些战略地点时，后方会派来增援（一共有三处）
  - 敌人可能会派遣空降单位偷袭，注意防守
  - 坦克和炮兵为有限资源，注意保护你的部队
  - 利用空中单位获取作战优势
  - 摧毁地方基地获得胜利
  - Score: 150 + 50(时间内完成) + 10 * (初始6炮兵存活数量)+ 15 * (初始坦克存活) - 1 * (每个生产的步兵(e1)) - 4*(每个生产的yak飞机)




#### 评分与日志上传

- 游戏自动生成包含关键指标（通关时间、击杀数、战损比等）的加密日志
- 参赛者将日志上传至官网（[link]）
- 组委会根据评估规则评分并更新排名
