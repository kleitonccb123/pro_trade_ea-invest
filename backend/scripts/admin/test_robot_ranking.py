#!/usr/bin/env python
"""
Test script para RobotRankingManager
"""

import sys
import os
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.dirname(__file__))

from app.gamification.robot_ranking_manager import RobotRankingManager

print("\n" + "="*60)
print("✅ RobotRankingManager - Teste de Funcionamento")
print("="*60)

for period in ['daily', 'weekly', 'monthly']:
    print(f"\n{RobotRankingManager.get_period_label(period)}")
    print("-" * 60)
    
    robots = RobotRankingManager.get_top_robots(period=period, limit=3)
    
    for robot in robots:
        profit_key = f"profit_{period.split('y')[0] if 'ly' in period else period}"
        if period == 'daily':
            profit_key = 'profit_24h'
        elif period == 'weekly':
            profit_key = 'profit_7d'
        else:
            profit_key = 'profit_15d'
        
        print(
            f"{robot['rank']:2d}. {robot['medal']} {robot['name']:30s} | "
            f"${robot.get(profit_key, 0):10.2f} | "
            f"{robot['win_rate']:5.1f}% | "
            f"👥 {robot['active_traders']:3d}"
        )

print("\n" + "="*60 + "\n✅ Teste concluído com sucesso!\n")
