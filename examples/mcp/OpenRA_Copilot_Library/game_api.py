import socket
import json
import time
import uuid
from typing import List, Optional, Tuple, Dict, Any
from .models import *

# API版本常量
API_VERSION = "1.0"

class GameAPIError(Exception):
    """游戏API异常基类"""
    def __init__(self, code: str, message: str, details: Dict = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"{code}: {message}")


class GameAPI:
    '''游戏API接口类，用于与游戏服务器进行通信
    提供了一系列方法来与游戏服务器进行交互，包括Actor移动、生产、查询等功能。
    所有的通信都是通过socket连接完成的。'''

    MAX_RETRIES = 3
    RETRY_DELAY = 0.5

    @staticmethod
    def is_server_running(host="localhost", port=7445, timeout=2.0) -> bool:
        '''检查游戏服务器是否已启动并可访问

        Args:
            host (str): 游戏服务器地址，默认为"localhost"。
            port (int): 游戏服务器端口，默认为 7445。
            timeout (float): 连接超时时间（秒），默认为 2.0 秒。

        Returns:
            bool: 服务器是否已启动并可访问
        '''
        try:
            request_data = {
                "apiVersion": API_VERSION,
                "requestId": str(uuid.uuid4()),
                "command": "ping",
                "params": {},
                "language": "zh"
            }

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((host, port))

                # 发送请求
                json_data = json.dumps(request_data)
                sock.sendall(json_data.encode('utf-8'))

                # 接收响应
                chunks = []
                while True:
                    try:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    except socket.timeout:
                        if chunks:
                            break
                        return False

                data = b''.join(chunks).decode('utf-8')

                try:
                    response = json.loads(data)
                    if response.get("status", 0) > 0 and "data" in response:
                        return True
                    return False
                except json.JSONDecodeError:
                    return False

        except (socket.error, ConnectionRefusedError, OSError):
            return False

        except Exception:
            return False

    def __init__(self, host, port=7445, language="zh"):
        self.server_address = (host, port)
        self.language = language
        '''初始化 GameAPI 类

        Args:
            host (str): 游戏服务器地址，本地就填"localhost"。
            port (int): 游戏服务器端口，默认为 7445。
            language (str): 接口返回语言，默认为 "zh"，支持 "zh" 和 "en"。
        '''

    def _generate_request_id(self) -> str:
        """生成唯一的请求ID"""
        return str(uuid.uuid4())

    def _send_request(self, command: str, params: dict) -> dict:
        '''通过socket和Game交互，发送信息并接收响应

        Args:
            command (str): 要执行的命令
            params (dict): 命令相关的数据参数

        Returns:
            dict: 服务器返回的JSON响应数据

        Raises:
            GameAPIError: 当API调用出现错误时
            ConnectionError: 当连接服务器失败时
        '''
        request_id = self._generate_request_id()
        request_data = {
            "apiVersion": API_VERSION,
            "requestId": request_id,
            "command": command,
            "params": params,
            "language": self.language
        }

        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(10)  # 设置超时时间
                    sock.connect(self.server_address)

                    # 发送请求
                    json_data = json.dumps(request_data)
                    sock.sendall(json_data.encode('utf-8'))

                    # 接收响应
                    response_data = self._receive_data(sock)

                    try:
                        response = json.loads(response_data)

                        # 验证响应格式
                        if not isinstance(response, dict):
                            raise GameAPIError("INVALID_RESPONSE",
                                             "服务器返回的响应格式无效")

                        # 检查请求ID匹配
                        if response.get("requestId") != request_id:
                            raise GameAPIError("REQUEST_ID_MISMATCH",
                                             "响应的请求ID不匹配")

                        # 处理错误响应
                        if response.get("status", 0) < 0:
                            error = response.get("error", {})
                            raise GameAPIError(
                                error.get("code", "UNKNOWN_ERROR"),
                                error.get("message", "未知错误"),
                                error.get("details")
                            )

                        return response

                    except json.JSONDecodeError:
                        raise GameAPIError("INVALID_JSON",
                                         "服务器返回的不是有效的JSON格式")

            except (socket.timeout, ConnectionError) as e:
                retries += 1
                if retries >= self.MAX_RETRIES:
                    raise GameAPIError("CONNECTION_ERROR",
                                     "连接服务器失败: {0}".format(str(e)))
                time.sleep(self.RETRY_DELAY)

            except GameAPIError:
                raise

            except Exception as e:
                raise GameAPIError("UNEXPECTED_ERROR",
                                 "发生未预期的错误: {0}".format(str(e)))

    def _receive_data(self, sock: socket.socket) -> str:
        """从socket接收完整的响应数据"""
        chunks = []
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            except socket.timeout:
                if not chunks:
                    raise GameAPIError("TIMEOUT",
                                     "接收响应超时")
                break
        return b''.join(chunks).decode('utf-8')

    def _handle_response(self, response: dict, error_msg: str) -> Any:
        """处理API响应，提取所需数据或抛出异常"""
        if response is None:
            raise GameAPIError("NO_RESPONSE",
                             "{0}".format(error_msg))
        return response.get("data") if "data" in response else response

    def move_camera_by_location(self, location: Location) -> None:
        '''根据给定的位置移动相机

        Args:
            location (Location): 要移动到的位置

        Raises:
            GameAPIError: 当移动相机失败时
        '''
        try:
            response = self._send_request('camera_move', {"location": location.to_dict()})
            self._handle_response(response, "移动相机失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("CAMERA_MOVE_ERROR",
                             "移动相机时发生错误: {0}".format(str(e)))

    def move_camera_by_direction(self, direction: str, distance: int) -> None:
        '''向某个方向移动相机

        Args:
            direction (str): 移动的方向，必须在 {ALL_DIRECTIONS} 中
            distance (int): 移动的距离

        Raises:
            GameAPIError: 当移动相机失败时
        '''
        try:
            response = self._send_request('camera_move', {
                "direction": direction,
                "distance": distance
            })
            self._handle_response(response, "移动相机失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("CAMERA_MOVE_ERROR", "移动相机时发生错误: {0}".format(str(e)))

    def can_produce(self, unit_type: str) -> bool:
        '''检查是否可以生产指定类型的Actor

        Args:
            unit_type (str): Actor类型，必须在 {ALL_UNITS} 中

        Returns:
            bool: 是否可以生产

        Raises:
            GameAPIError: 当查询生产能力失败时
        '''
        try:
            response = self._send_request('query_can_produce', {
                "units": [{"unit_type": unit_type}]
            })
            result = self._handle_response(response, "查询生产能力失败")
            return result.get("canProduce", False)
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("PRODUCE_QUERY_ERROR", "查询生产能力时发生错误: {0}".format(str(e)))

    def produce(self, unit_type: str, quantity: int, auto_place_building: bool = False) -> Optional[int]:
        '''生产指定数量的Actor

        Args:
            unit_type (str): Actor类型
            quantity (int): 生产数量
            auto_place_building (bool, optional): 是否在生产完成后使用随机位置自动放置建筑，仅对建筑类型有效

        Returns:
            int: 生产任务的 waitId
            None: 如果任务创建失败

        Raises:
            GameAPIError: 当生产命令执行失败时
        '''
        try:
            response = self._send_request('start_production', {
                "units": [{"unit_type": unit_type, "quantity": quantity}],
                "autoPlaceBuilding": auto_place_building
            })
            result = self._handle_response(response, "生产命令执行失败")
            return result.get("waitId")
        except GameAPIError as e:
            if e.code == "COMMAND_EXECUTION_ERROR":
                return None
            raise
        except Exception as e:
            raise GameAPIError("PRODUCTION_ERROR", "执行生产命令时发生错误: {0}".format(str(e)))

    def produce_wait(self, unit_type: str, quantity: int, auto_place_building: bool = True) -> None:
        '''生产指定数量的Actor并等待生产完成

        Args:
            unit_type (str): Actor类型
            quantity (int): 生产数量
            auto_place_building (bool, optional): 是否在生产完成后使用随机位置自动放置建筑，仅对建筑类型有效

        Raises:
            GameAPIError: 当生产或等待过程中发生错误时
        '''
        try:
            wait_id = self.produce(unit_type, quantity, auto_place_building)
            if wait_id is not None:
                self.wait(wait_id, 20 * quantity)
            else:
                raise GameAPIError("PRODUCTION_FAILED",
                                 "生产任务创建失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("PRODUCTION_WAIT_ERROR", "生产并等待过程中发生错误: {0}".format(str(e)))

    def is_ready(self, wait_id: int) -> bool:
        '''检查生产任务是否完成

        Args:
            wait_id (int): 生产任务的 ID

        Returns:
            bool: 是否完成

        Raises:
            GameAPIError: 当查询任务状态失败时
        '''
        try:
            response = self._send_request('query_wait_info', {"waitId": wait_id})
            result = self._handle_response(response, "查询任务状态失败")
            return result.get("status", False)
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("WAIT_STATUS_ERROR", "查询任务状态时发生错误: {0}".format(str(e)))

    def wait(self, wait_id: int, max_wait_time: float = 20.0) -> bool:
        '''等待生产任务完成

        Args:
            wait_id (int): 生产任务的 ID
            max_wait_time (float): 最大等待时间，默认为 20 秒

        Returns:
            bool: 是否成功完成等待（false表示超时）

        Raises:
            GameAPIError: 当等待过程中发生错误时
        '''
        try:
            wait_time = 0.0
            step_time = 0.1
            while True:
                response = self._send_request('query_wait_info', {"waitId": wait_id})
                result = self._handle_response(response, "等待任务完成失败")

                if result.get("waitStatus") == "success":
                    return True

                time.sleep(step_time)
                wait_time += step_time
                if wait_time > max_wait_time:
                    return False

        except GameAPIError as e:
            if e.code == "COMMAND_EXECUTION_ERROR":
                return True  # 特殊情况：如果命令执行错误，可能是任务已完成
            raise
        except Exception as e:
            raise GameAPIError("WAIT_ERROR", "等待任务完成时发生错误: {0}".format(str(e)))

    def move_units_by_location(self, actors: List[Actor], location: Location, attack_move: bool = False) -> None:
        '''移动单位到指定位置

        Args:
            actors (List[Actor]): 要移动的Actor列表
            location (Location): 目标位置
            attack_move (bool): 是否为攻击性移动

        Raises:
            GameAPIError: 当移动命令执行失败时
        '''
        try:
            response = self._send_request('move_actor', {
                "targets": {"actorId": [actor.actor_id for actor in actors]},
                "location": location.to_dict(),
                "isAttackMove": 1 if attack_move else 0
            })
            self._handle_response(response, "移动单位失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("MOVE_UNITS_ERROR", "移动单位时发生错误: {0}".format(str(e)))

    def move_units_by_direction(self, actors: List[Actor], direction: str, distance: int) -> None:
        '''向指定方向移动单位

        Args:
            actors (List[Actor]): 要移动的Actor列表
            direction (str): 移动方向
            distance (int): 移动距离

        Raises:
            GameAPIError: 当移动命令执行失败时
        '''
        try:
            response = self._send_request('move_actor', {
                "targets": {"actorId": [actor.actor_id for actor in actors]},
                "direction": direction,
                "distance": distance
            })
            self._handle_response(response, "移动单位失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("MOVE_UNITS_ERROR", "移动单位时发生错误: {0}".format(str(e)))

    def move_units_by_path(self, actors: List[Actor], path: List[Location]) -> None:
        '''沿路径移动单位

        Args:
            actors (List[Actor]): 要移动的Actor列表
            path (List[Location]): 移动路径

        Raises:
            GameAPIError: 当移动命令执行失败时
        '''
        if not path:
            return
        try:
            response = self._send_request('move_actor', {
                "targets": {"actorId": [actor.actor_id for actor in actors]},
                "path": [point.to_dict() for point in path]
            })
            self._handle_response(response, "移动单位失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("MOVE_UNITS_ERROR", "移动单位时发生错误: {0}".format(str(e)))

    def select_units(self, query_params: TargetsQueryParam) -> None:
        '''选中符合条件的Actor，指的是游戏中的选中操作

        Args:
            query_params (TargetsQueryParam): 查询参数

        Raises:
            GameAPIError: 当选择单位失败时
        '''
        try:
            response = self._send_request('select_unit', {
                "targets": query_params.to_dict()
            })
            self._handle_response(response, "选择单位失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("SELECT_UNITS_ERROR", "选择单位时发生错误: {0}".format(str(e)))

    def form_group(self, actors: List[Actor], group_id: int) -> None:
        '''将Actor编成编组

        Args:
            actors (List[Actor]): 要分组的Actor列表
            group_id (int): 群组 ID

        Raises:
            GameAPIError: 当编组失败时
        '''
        try:
            response = self._send_request('form_group', {
                "targets": {"actorId": [actor.actor_id for actor in actors]},
                "groupId": group_id
            })
            self._handle_response(response, "编组失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("FORM_GROUP_ERROR", "编组时发生错误: {0}".format(str(e)))

    def query_actor(self, query_params: TargetsQueryParam) -> List[Actor]:
        '''查询符合条件的Actor，获取Actor应该使用的接口

        Args:
            query_params (TargetsQueryParam): 查询参数

        Returns:
            List[Actor]: 符合条件的Actor列表

        Raises:
            GameAPIError: 当查询Actor失败时
        '''
        try:
            response = self._send_request('query_actor', {
                "targets": query_params.to_dict()
            })
            result = self._handle_response(response, "查询Actor失败")

            actors = []
            actors_data = result.get("actors", [])

            for data in actors_data:
                try:
                    actor = Actor(data["id"])
                    position = Location(
                        data["position"]["x"],
                        data["position"]["y"]
                    )
                    hp_percent = data["hp"] * 100 // data["maxHp"] if data["maxHp"] > 0 else -1
                    actor.update_details(
                        data["type"],
                        data["faction"],
                        position,
                        hp_percent
                    )
                    actors.append(actor)
                except KeyError as e:
                    raise GameAPIError("INVALID_ACTOR_DATA", "Actor数据格式无效: {0}".format(str(e)))

            return actors

        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("QUERY_ACTOR_ERROR", "查询Actor时发生错误: {0}".format(str(e)))

    def find_path(self, actors: List[Actor], destination: Location, method: str) -> List[Location]:
        '''为Actor找到到目标的路径

        Args:
            actors (List[Actor]): 要移动的Actor列表
            destination (Location): 目标位置
            method (str): 寻路方法，必须在 {"最短路"，"左路"，"右路"} 中

        Returns:
            List[Location]: 路径点列表，第0个是目标点，最后一个是Actor当前位置，相邻的点都是八方向相连的点

        Raises:
            GameAPIError: 当寻路失败时
        '''
        try:
            response = self._send_request('query_path', {
                "targets": {"actorId": [actor.actor_id for actor in actors]},
                "destination": destination.to_dict(),
                "method": method
            })
            result = self._handle_response(response, "寻路失败")

            try:
                return [Location(step["x"], step["y"]) for step in result["path"]]
            except (KeyError, TypeError) as e:
                raise GameAPIError("INVALID_PATH_DATA", "路径数据格式无效: {0}".format(str(e)))

        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("FIND_PATH_ERROR", "寻路时发生错误: {0}".format(str(e)))

    def get_actor_by_id(self, actor_id: int) -> Optional[Actor]:
        '''获取指定 ID 的Actor，这是根据ActorID获取Actor的接口，只有已知ActorID是才能调用这个接口

        Args:
            actor_id (int): Actor ID

        Returns:
            Actor: 对应的Actor
            None: 如果Actor不存在

        Raises:
            GameAPIError: 当获取Actor失败时
        '''
        actor = Actor(actor_id)
        try:
            if self.update_actor(actor):
                return actor
            return None
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("GET_ACTOR_ERROR", "获取Actor时发生错误: {0}".format(str(e)))

    def update_actor(self, actor: Actor) -> bool:
        '''更新Actor信息，如果时间改变了，需要调用这个来更新Actor的各种属性（位置等）。

        Args:
            actor (Actor): 要更新的Actor

        Returns:
            bool: 如果Actor已死，会返回false，否则返回true

        Raises:
            GameAPIError: 当更新Actor信息失败时
        '''
        try:
            response = self._send_request('query_actor', {
                "targets": {"actorId": [actor.actor_id]}
            })
            result = self._handle_response(response, "更新Actor信息失败")

            try:
                actor_data = result["actors"][0]
                position = Location(
                    actor_data["position"]["x"],
                    actor_data["position"]["y"]
                )
                hp_percent = actor_data["hp"] * 100 // actor_data["maxHp"] if actor_data["maxHp"] > 0 else -1
                actor.update_details(
                    actor_data["type"],
                    actor_data["faction"],
                    position,
                    hp_percent
                )
                return True
            except (IndexError, KeyError) as e:
                return False

        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("UPDATE_ACTOR_ERROR", "更新Actor信息时发生错误: {0}".format(str(e)))

    def deploy_units(self, actors: List[Actor]) -> None:
        '''部署/展开 Actor

        Args:
            actors (List[Actor]): 要部署/展开的Actor列表

        Raises:
            GameAPIError: 当部署单位失败时
        '''
        try:
            response = self._send_request('deploy', {
                "targets": {"actorId": [actor.actor_id for actor in actors]}
            })
            self._handle_response(response, "部署单位失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("DEPLOY_UNITS_ERROR", "部署单位时发生错误: {0}".format(str(e)))

    def move_camera_to(self, actor: Actor) -> None:
        '''将相机移动到指定Actor位置

        Args:
            actor (Actor): 目标Actor

        Raises:
            GameAPIError: 当移动相机失败时
        '''
        try:
            response = self._send_request('view', {"actorId": actor.actor_id})
            self._handle_response(response, "移动相机失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("CAMERA_MOVE_ERROR", "移动相机时发生错误: {0}".format(str(e)))

    def occupy_units(self, occupiers: List[Actor], targets: List[Actor]) -> None:
        '''占领目标

        Args:
            occupiers (List[Actor]): 执行占领的Actor列表
            targets (List[Actor]): 被占领的目标列表

        Raises:
            GameAPIError: 当占领行动失败时
        '''
        try:
            response = self._send_request('occupy', {
                "occupiers": {"actorId": [actor.actor_id for actor in occupiers]},
                "targets": {"actorId": [target.actor_id for target in targets]}
            })
            self._handle_response(response, "占领行动失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("OCCUPY_ERROR", "占领行动时发生错误: {0}".format(str(e)))

    def attack_target(self, attacker: Actor, target: Actor) -> bool:
        '''攻击指定目标

        Args:
            attacker (Actor): 发起攻击的Actor
            target (Actor): 被攻击的目标

        Returns:
            bool: 是否成功发起攻击(如果目标不可见，或者不可达，或者攻击者已经死亡，都会返回false)

        Raises:
            GameAPIError: 当攻击命令执行失败时
        '''
        try:
            response = self._send_request('attack', {
                "attackers": {"actorId": [attacker.actor_id]},
                "targets": {"actorId": [target.actor_id]}
            })
            result = self._handle_response(response, "攻击命令执行失败")
            return response.get("status", 0) > 0
        except GameAPIError as e:
            if e.code == "COMMAND_EXECUTION_ERROR":
                return False
            raise
        except Exception as e:
            raise GameAPIError("ATTACK_ERROR", "攻击命令执行时发生错误: {0}".format(str(e)))

    def can_attack_target(self, attacker: Actor, target: Actor) -> bool:
        '''检查是否可以攻击目标

        Args:
            attacker (Actor): 攻击者
            target (Actor): 目标

        Returns:
            bool: 是否可以攻击

        Raises:
            GameAPIError: 当检查攻击能力失败时
        '''
        try:
            response = self._send_request('query_actor', {
                "targets": {
                    "actorId": [target.actor_id],
                    "restrain": [{"visible": True}]
                }
            })
            result = self._handle_response(response, "检查攻击能力失败")
            return len(result.get("actors", [])) > 0
        except GameAPIError:
            return False
        except Exception as e:
            raise GameAPIError("CHECK_ATTACK_ERROR", "检查攻击能力时发生错误: {0}".format(str(e)))

    def repair_units(self, actors: List[Actor]) -> None:
        '''修复Actor

        Args:
            actors (List[Actor]): 要修复的Actor列表，可以是载具或者建筑，修理载具需要修建修理中心

        Raises:
            GameAPIError: 当修复命令执行失败时
        '''
        try:
            response = self._send_request('repair', {
                "targets": {"actorId": [actor.actor_id for actor in actors]}
            })
            self._handle_response(response, "修复命令执行失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("REPAIR_ERROR", "修复命令执行时发生错误: {0}".format(str(e)))

    def stop(self, actors: List[Actor]) -> None:
        '''停止Actor当前行动

        Args:
            actors (List[Actor]): 要停止的Actor列表

        Raises:
            GameAPIError: 当停止命令执行失败时
        '''
        try:
            response = self._send_request('stop', {
                "targets": {"actorId": [actor.actor_id for actor in actors]}
            })
            self._handle_response(response, "停止命令执行失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("STOP_ERROR", "停止命令执行时发生错误: {0}".format(str(e)))

    def visible_query(self, location: Location) -> bool:
        '''查询位置是否可见

        Args:
            location (Location): 要查询的位置

        Returns:
            bool: 是否可见

        Raises:
            GameAPIError: 当查询可见性失败时
        '''
        try:
            response = self._send_request('fog_query', {
                "pos": location.to_dict()
            })
            result = self._handle_response(response, "查询可见性失败")
            return result.get('IsVisible', False)
        except GameAPIError:
            return False
        except Exception as e:
            raise GameAPIError("VISIBILITY_QUERY_ERROR", "查询可见性时发生错误: {0}".format(str(e)))

    def explorer_query(self, location: Location) -> bool:
        '''查询位置是否已探索

        Args:
            location (Location): 要查询的位置

        Returns:
            bool: 是否已探索

        Raises:
            GameAPIError: 当查询探索状态失败时
        '''
        try:
            response = self._send_request('fog_query', {
                "pos": location.to_dict()
            })
            result = self._handle_response(response, "查询探索状态失败")
            return result.get('IsExplored', False)
        except GameAPIError:
            return False
        except Exception as e:
            raise GameAPIError("EXPLORER_QUERY_ERROR", "查询探索状态时发生错误: {0}".format(str(e)))

    def query_production_queue(self, queue_type: str) -> dict:
        '''查询指定类型的生产队列

        Args:
            queue_type (str): 队列类型，必须是以下值之一：
                'Building' - 建筑
                'Defense' - 防御
                'Infantry' - 士兵
                'Vehicle' - 载具
                'Aircraft' - 飞机
                'Naval' - 海军

        Returns:
            dict: 包含队列信息的字典，格式如下：
                {
                    "queue_type": "队列类型",
                    "queue_items": [
                        {
                            "name": "项目内部名称",
                            "chineseName": "项目中文名称",
                            "remaining_time": 剩余时间,
                            "total_time": 总时间,
                            "remaining_cost": 剩余花费,
                            "total_cost": 总花费,
                            "paused": 是否暂停,
                            "done": 是否完成,
                            "progress_percent": 完成百分比,
                            "owner_actor_id": 所属建筑的ActorID,
                            "status": "项目状态，可能的值：
                                'completed' - 已完成
                                'paused' - 已暂停
                                'in_progress' - 正在建造（队列中第一个项目）
                                'waiting' - 等待中（队列中其他项目）"
                        },
                        ...
                    ],
                    "has_ready_item": 是否有已就绪的项目
                }

        Raises:
            GameAPIError: 当查询生产队列失败时
        '''
        if queue_type not in ['Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 'Naval']:
            raise GameAPIError(
                "INVALID_QUEUE_TYPE",
                "队列类型必须是以下值之一: 'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 'Naval'")

        try:
            response = self._send_request('query_production_queue', {
                "queueType": queue_type
            })
            return self._handle_response(response, "查询生产队列失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("PRODUCTION_QUEUE_QUERY_ERROR", "查询生产队列时发生错误: {0}".format(str(e)))

    def place_building(self, queue_type: str, location: Location = None) -> None:
        '''放置建造队列顶端已就绪的建筑

        Args:
            queue_type (str): 队列类型，可选值：'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 'Naval'
            location (Location, optional): 放置建筑的位置，如果不指定则使用自动选择的位置

        Raises:
            GameAPIError: 当放置建筑失败时
        '''
        try:
            params = {
                "queueType": queue_type
            }
            if location:
                params["location"] = location.to_dict()

            response = self._send_request('place_building', params)
            self._handle_response(response, "放置建筑失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("PLACE_BUILDING_ERROR", "放置建筑时发生错误: {0}".format(str(e)))

    def manage_production(self, queue_type: str, action: str) -> None:
        '''管理生产队列中的项目（暂停/取消/继续）

        Args:
            queue_type (str): 队列类型，可选值：'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 'Naval'
            action (str): 操作类型，必须是 'pause', 'cancel', 或 'resume'

        Raises:
            GameAPIError: 当管理生产队列失败时
        '''
        if action not in ['pause', 'cancel', 'resume']:
            raise GameAPIError("INVALID_ACTION", "action参数必须是 'pause', 'cancel', 或 'resume'")

        try:
            params = {
                "queueType": queue_type,
                "action": action
            }

            response = self._send_request('manage_production', params)
            self._handle_response(response, "管理生产队列失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("MANAGE_PRODUCTION_ERROR", "管理生产队列时发生错误: {0}".format(str(e)))

    # ===== 依赖关系表 =====

    BUILDING_DEPENDENCIES = {
        "电厂": [],
        "兵营": ["电厂"],
        "矿场": ["电厂"],
        "车间": ["矿场"],
        "雷达": ["矿场"],
        "维修中心": ["车间"],
        "核电": ["雷达"],
        "科技中心": ["车间", "雷达"],
        "机场": ["雷达"]
    }

    UNIT_DEPENDENCIES = {
        "步兵": ["兵营"],
        "火箭兵": ["兵营"],
        "工程师": ["兵营"],
        "手雷兵": ["兵营"],
        "矿车": ["车间"],
        "防空车": ["车间"],
        "装甲车": ["车间"],
        "重坦": ["车间", "维修中心"],
        "v2": ["车间", "雷达"],
        "猛犸坦克": ["车间", "维修中心", "科技中心"]
    }

    def deploy_mcv_and_wait(self, wait_time: float = 1.0) -> None:
        '''展开自己的基地车并等待一小会
        Args:
            wait_time (float): 展开后的等待时间(秒)，默认为1秒，已经够了，一般不用改
        '''
        mcv = self.query_actor(TargetsQueryParam(type=['mcv'], faction='自己'))
        if not mcv:
            return
        self.deploy_units(mcv)
        time.sleep(wait_time)

    def ensure_can_build_wait(self, building_name: str) -> bool:
        '''确保能生产某个建筑，如果不能会尝试生产所有前置建筑，并等待生产完成
        Args:
            building_name (str): 建筑名称(中文)
        Returns:
            bool: 是否已经拥有该建筑或成功生产
        '''
        building_exists = self.query_actor(
            TargetsQueryParam(type=[building_name], faction="自己"))
        if building_exists:
            return True

        # 检查该建筑的依赖
        deps = self.BUILDING_DEPENDENCIES.get(building_name, [])
        for dep in deps:
            if not self.ensure_building_wait_buildself(dep):
                return False

        return self.ensure_building_wait_buildself(building_name)

    def ensure_building_wait_buildself(self, building_name: str) -> bool:
        '''
        非外部接口
        '''
        building_exists = self.query_actor(
            TargetsQueryParam(type=[building_name], faction="自己"))
        if building_exists:
            return True

        # 检查该建筑的依赖
        deps = self.BUILDING_DEPENDENCIES.get(building_name, [])
        for dep in deps:
            self.ensure_building_wait_buildself(dep)

        if self.can_produce(building_name):
            wait_id = self.produce(building_name, 1, True)
            if wait_id:
                self.wait(wait_id)
                return True
        return False

    def ensure_can_produce_unit(self, unit_name: str) -> bool:
        '''确保能生产某个Actor(会自动生产其所需建筑并等待完成)
        Args:
            unit_name (str): Actor名称(中文)
        Returns:
            bool: 是否成功准备好生产该Actor
        '''
        if self.can_produce(unit_name):
            return True
        # 根据UNIT_DEPENDENCIES找到依赖的建筑
        needed_buildings = self.UNIT_DEPENDENCIES.get(unit_name, [])
        for b in needed_buildings:
            self.ensure_building_wait_buildself(b)
        # 如果依赖全部OK还是生产不出来，可能是什么东西没修好，稍微等一下
        if not self.can_produce(unit_name):
            time.sleep(1)
        return self.can_produce(unit_name)

    def get_unexplored_nearby_positions(self, map_query_result: MapQueryResult, current_pos: Location,
                                        max_distance: int) -> List[Location]:
        '''获取当前位置附近尚未探索的坐标列表
        Args:
            map_query_result (MapQueryResult): 地图信息
            current_pos (Location): 当前Actor的位置
            max_distance (int): 距离范围(曼哈顿)
        Returns:
            List[Location]: 未探索位置列表
        '''
        neighbors = []
        for dx in range(-max_distance, max_distance + 1):
            for dy in range(-max_distance, max_distance + 1):
                if abs(dx) + abs(dy) > max_distance:
                    continue
                if dx == 0 and dy == 0:
                    continue
                x = current_pos.x + dx
                y = current_pos.y + dy
                if 0 <= x < map_query_result.MapWidth and 0 <= y < map_query_result.MapHeight:
                    if not map_query_result.IsExplored[x][y]:
                        neighbors.append(Location(x, y))
        return neighbors

    def move_units_by_location_and_wait(self, actors: List[Actor], location: Location,
                                        max_wait_time: float = 10.0, tolerance_dis: int = 1) -> bool:
        '''移动一批Actor到指定位置，并等待(或直到超时)
        Args:
            actors (List[Actor]): 要移动的Actor列表
            location (Location): 目标位置
            max_wait_time (float): 最大等待时间(秒)
            tolerance_dis (int): 容忍的距离误差，Actor：格子，Actor越多一般就得设得越大
        Returns:
            bool: 是否在max_wait_time内到达(若中途卡住或超时则False)
        '''
        self.move_units_by_location(actors, location)
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            all_arrived = True
            for actor in actors:
                self.update_actor(actor)
                if actor.position.manhattan_distance(location) > tolerance_dis:
                    all_arrived = False
                    break
            if all_arrived:
                return True
            time.sleep(0.3)
        return False

    def unit_attribute_query(self, actors: List[Actor]) -> dict:
        '''查询Actor的属性和攻击范围内目标

        Args:
            actors (List[Actor]): 要查询的Actor列表

        Returns:
            dict: Actor属性信息，包括攻击范围内的目标

        Raises:
            GameAPIError: 当查询Actor属性失败时
        '''
        try:
            response = self._send_request('unit_attribute_query', {
                "targets": {"actorId": [actor.actor_id for actor in actors]}
            })
            return self._handle_response(response, "查询Actor属性失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("ATTRIBUTE_QUERY_ERROR", "查询Actor属性时发生错误: {0}".format(str(e)))

    # 保留旧方法作为兼容性别名，调用新的合并方法
    def unit_range_query(self, actors: List[Actor]) -> List[int]:
        '''获取这些传入Actor攻击范围内的所有Target (已弃用，请使用unit_attribute_query)

        Args:
            actors (List[Actor]): 要查询的Actor列表

        Returns:
            List[int]: 攻击范围内的目标ID列表
        '''
        try:
            result = self.unit_attribute_query(actors)
            # 提取所有目标ID
            targets = []
            for attr in result.get("attributes", []):
                targets.extend(attr.get("targets", []))
            return targets
        except Exception:
            return []

    def map_query(self) -> MapQueryResult:
        '''查询地图信息

        Returns:
            MapQueryResult: 地图查询结果

        Raises:
            GameAPIError: 当查询地图信息失败时
        '''
        try:
            response = self._send_request('map_query', {})
            result = self._handle_response(response, "查询地图信息失败")

            return MapQueryResult(
                MapWidth=result.get('MapWidth', 0),
                MapHeight=result.get('MapHeight', 0),
                Height=result.get('Height', [[]]),
                IsVisible=result.get('IsVisible', [[]]),
                IsExplored=result.get('IsExplored', [[]]),
                Terrain=result.get('Terrain', [[]]),
                ResourcesType=result.get('ResourcesType', [[]]),
                Resources=result.get('Resources', [[]])
            )
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("MAP_QUERY_ERROR", "查询地图信息时发生错误: {0}".format(str(e)))

    def player_base_info_query(self) -> PlayerBaseInfo:
        '''查询玩家基地信息

        Returns:
            PlayerBaseInfo: 玩家基地信息

        Raises:
            GameAPIError: 当查询玩家基地信息失败时
        '''
        try:
            response = self._send_request('player_baseinfo_query', {})
            result = self._handle_response(response, "查询玩家基地信息失败")

            return PlayerBaseInfo(
                Cash=result.get('Cash', 0),
                Resources=result.get('Resources', 0),
                Power=result.get('Power', 0),
                PowerDrained=result.get('PowerDrained', 0),
                PowerProvided=result.get('PowerProvided', 0)
            )
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("BASE_INFO_QUERY_ERROR", "查询玩家基地信息时发生错误: {0}".format(str(e)))

    def screen_info_query(self) -> ScreenInfoResult:
        '''查询当前玩家看到的屏幕信息

        Returns:
            ScreenInfoResult: 屏幕信息查询结果

        Raises:
            GameAPIError: 当查询屏幕信息失败时
        '''
        try:
            response = self._send_request('screen_info_query', {})
            result = self._handle_response(response, "查询屏幕信息失败")

            return ScreenInfoResult(
                ScreenMin=Location(
                    result['ScreenMin']['X'],
                    result['ScreenMin']['Y']
                ),
                ScreenMax=Location(
                    result['ScreenMax']['X'],
                    result['ScreenMax']['Y']
                ),
                IsMouseOnScreen=result.get('IsMouseOnScreen', False),
                MousePosition=Location(
                    result['MousePosition']['X'],
                    result['MousePosition']['Y']
                )
            )
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("SCREEN_INFO_QUERY_ERROR", "查询屏幕信息时发生错误: {0}".format(str(e)))

    def set_rally_point(self, actors: list[Actor], target_location: Location) -> None:
        '''设置建筑的集结点

        Args:
            actors (list[Actor]): 要设置集结点的建筑列表
            target_location (Location): 集结点目标位置

        Raises:
            GameAPIError: 当设置集结点失败时
        '''
        try:
            response = self._send_request('set_rally_point', {
                "targets": {"actorId": [actor.actor_id for actor in actors]},
                "location": target_location.to_dict()
            })
            self._handle_response(response, "设置集结点失败")
        except GameAPIError:
            raise
        except Exception as e:
            raise GameAPIError("SET_RALLY_POINT_ERROR", "设置集结点时发生错误: {0}".format(str(e)))
