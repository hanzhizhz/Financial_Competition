"""行程单模型 - 航空/铁路/巴士等交通凭证"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Itinerary:
    """行程单（航空/铁路/巴士等交通凭证）结构化数据"""
    
    # 交通类型
    transport_type: str = ""  # 民航|高铁|动车|普速|长途巴士|地铁
    ticket_number: str = ""  # 票号/订单号
    
    # 乘客信息
    passenger_name: str = ""  # 乘客姓名
    id_card_number: str = ""  # 身份证号码
    
    # 行程信息
    departure_station: str = ""  # 出发站
    arrival_station: str = ""  # 到达站
    departure_datetime: Optional[datetime] = None  # 出发时间
    arrival_datetime: Optional[datetime] = None  # 到达时间
    flight_train_number: str = ""  # 航班号/车次号 (如 G1234 或 CA1832)
    
    # 座位信息
    seat_class: str = ""  # 经济舱|商务舱|一等座|二等座
    seat_number: str = ""  # 座位号
    
    # 费用明细
    base_fare: float = 0.0  # 基础票价
    fuel_surcharge: float = 0.0  # 燃油附加费
    airport_railway_fee: float = 0.0  # 机场建设费/铁路建设费
    insurance_fee: float = 0.0  # 保险费
    total_amount: float = 0.0  # 总金额
    
    # 支付方式
    payment_method: str = ""  # 支付宝|微信|银联


__all__ = ["Itinerary"]

