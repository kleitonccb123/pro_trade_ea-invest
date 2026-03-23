//+------------------------------------------------------------------+
//| Expert Advisor: PRICEPRO_M15                                     |
//| Variante: CLASSIC REFINED — Gráfico M15                          |
//| Estratégia: Versão refinada do clássico PRICEPRO_MONEY           |
//| Lógica: Todos 4 filtros ativos + filtro adicional de               |
//|          Confirmação Tripla: EMA + RSI + Candle de força           |
//|          na mesma direção                                          |
//|          EMA 55 (padrão original) + RSI 9 + níveis 33/66          |
//|          Adicionado: filtro de horário (evita abertura no spread)  |
//+------------------------------------------------------------------+
#property copyright "PRICEPRO"
#property link      "https://www.greaterwaves.com"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| LICENÇA
//+------------------------------------------------------------------+
#define LICENSE_DOMAIN      "pricepro-licencas.site"
#define LICENSE_ENDPOINT    "/api.php?conta="
#define LICENSE_TIMEOUT     5000
#define LICENSE_MAX_RETRIES 3

bool     g_licenseValidated = false;
datetime g_licenseExpire    = 0;
string   g_licenseAccountID = "";

bool CheckLicense()
{
   long account_login = AccountInfoInteger(ACCOUNT_LOGIN);
   if(account_login <= 0) { Alert("ERRO: conta inválida"); return false; }
   string login = IntegerToString((int)account_login);
   g_licenseAccountID = login;
   string protos[2] = {"https://", "http://"};
   for(int p = 0; p < 2; p++)
   {
      string url = protos[p] + LICENSE_DOMAIN + LICENSE_ENDPOINT + login;
      for(int attempt = 0; attempt < LICENSE_MAX_RETRIES; attempt++)
      {
         if(ValidarLicencaViaAPI(url)) return true;
         if(attempt < LICENSE_MAX_RETRIES - 1) Sleep(2000);
      }
   }
   Alert("ERRO: Licença inválida. Contate: pricepro-licencas.site");
   return false;
}
bool ValidarLicencaViaAPI(const string url)
{
   uchar post[], result[]; string rh="",h=""; ArrayResize(result,0);
   int res=WebRequest("GET",url,h,LICENSE_TIMEOUT,post,result,rh);
   if(res==-1){Print("WebRequest falhou: ",url," | Erro: ",GetLastError());return false;}
   string response=CharArrayToString(result,0,ArraySize(result)), ru=response; StringToUpper(ru);
   if(StringFind(ru,"AUTORIZAD")>=0||StringFind(ru,"AUTHORIZED")>=0){ProcessarRespostaLicenca(response);g_licenseValidated=true;Comment("✓ Licença: "+g_licenseAccountID);return true;}
   return false;
}
void ProcessarRespostaLicenca(const string response)
{
   uchar arr[]; int len=StringToCharArray(response,arr);
   for(int i=0;i<len;i++){if(arr[i]>='0'&&arr[i]<='9'){int j=i;while(j<len&&arr[j]>='0'&&arr[j]<='9')j++;if(j-i>=8){g_licenseExpire=(datetime)StringToInteger(StringSubstr(response,i,j-i));break;}i=j;}}
}

//+------------------------------------------------------------------+
//| PARÂMETROS — CLASSIC REFINED M15
//+------------------------------------------------------------------+
input bool   AtivarEA              = true;
input bool   ModoDebug             = false;

//--- Filtros (4 originais + HorárioFiltro)
input bool   UsarRSI               = true;
input bool   RSI_ImpulsoMode       = false; // retração (original)
input bool   UsarForcaCandle       = true;
input bool   UsarVolume            = true;
input bool   UsarRangeAdaptativo   = true;

//--- Filtro de Horário: evitar primeiros e últimos 30min de sessão (spread alto)
input bool   UsarFiltroHorario     = true;
input int    HoraInicioPermitido   = 8;     // Hora de início permitida (servidor)
input int    MinutoInicioPermitido = 30;    // Minuto de início (evita abertura de sessão)
input int    HoraFimPermitido      = 17;    // Hora de fim (antes do fechamento NY)
input int    MinutoFimPermitido    = 30;    // Minuto de fim

//--- Volume/Lote
input bool   UsarLoteFixo          = true;
input double LoteFixo              = 0.05;
input bool   UsarLotePorRisco      = false;
input double PercentualRisco       = 10.0;

//--- Média Móvel — EMA 55 (original PRICEPRO)
input bool   AtivarMediaMovel      = true;
input int    PeriodoMediaMovel     = 55;
input ENUM_MA_METHOD TipoMedia     = MODE_EMA;

//--- RSI — período 9, níveis originais
input int    PeriodoRSI            = 9;
input double RSI_Sobrecomprado     = 66.0;
input double RSI_Sobrevendido      = 33.0;

//--- Candle 40% original
input double CorpoCandleMinimo     = 40.0;

//--- Volume 0.55 original
input double VolumeMinimo          = 0.55;

//--- Range 1.15 original
input int    PeriodoRange          = 9;
input double MultiplicadorRange    = 1.15;

//--- TP/SL originais
input double TP_USD                = 10.0;
input double SL_USD                = 10.0;

//--- Gestão Financeira
input double MetaDiaria            = 0.0;
input double LimitePercaDiaria     = 0.0;
input double DrawdownEmergencia    = 50.0;

//--- Geral
input ulong  NumeroMagico          = 20260003;
input ENUM_TIMEFRAMES TempoGrafico = PERIOD_M15;

//--- Breakeven 500 (original)
input int    BreakevenActivatePoints = 500;
input bool   AtivarTrailingPorCandle = true;
input int    MinMovePoints           = 1;

//+------------------------------------------------------------------+
//| Globais
//+------------------------------------------------------------------+
CTrade trade;
int    ema_handle = INVALID_HANDLE;
int    rsi_handle = INVALID_HANDLE;

double g_MetaDiaria=0.0,g_LimitePercaDiaria=0.0;
bool   g_AtivarEA=true,g_dailyBlocked=false,g_emergencyBlocked=false;
double g_initialEquity=0.0;
datetime g_lastBarTime=0;

#define PP_BG     "M15_BG"
#define PP_TITLE  "M15_TITLE"
#define PP_PROFIT "M15_PROFIT"
#define PP_VALUE  "M15_VALUE"
color C_BG_DARK=C'15,25,50'; color C_TXT=clrWhite; color C_OK=clrLime; color C_BAD=clrRed;

ulong  g_lastStatsUpdateTick=0; double g_cachedDailyProfit=0.0;
ulong  g_lastPanelUpdate=0,g_lastHasPosTick=0; bool g_cachedHasPos=false;
ulong    g_breakevenTickets[];
datetime g_breakevenLastModifiedBar[];

#define DIR_NONE  0
#define DIR_BUY   1
#define DIR_SELL -1

//+------------------------------------------------------------------+
double PipSize(){int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);return (d==3||d==5)?_Point*10.0:_Point;}
double MoneyToPriceDistance(double money,double volume){if(money<=0.0||volume<=0.0)return 0.0;double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE),ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);return(tv>0.0&&ts>0.0)?(money*ts)/(tv*volume):0.0;}
double CalculateLotSize(){double lot=0.01;if(UsarLoteFixo)lot=LoteFixo;else if(UsarLotePorRisco)lot=(AccountInfoDouble(ACCOUNT_BALANCE)*(PercentualRisco/100.0))/1000.0;double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),st=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);if(mn>0.0)lot=MathMax(lot,mn);if(mx>0.0)lot=MathMin(lot,mx);if(st>0.0)lot=MathRound(lot/st)*st;return NormalizeDouble(lot,2);}
bool IsNewBar(){datetime t=iTime(_Symbol,PERIOD_CURRENT,0);if(t!=0&&t!=g_lastBarTime){g_lastBarTime=t;return true;}return false;}
bool GetEMA(double &v){v=0.0;if(ema_handle==INVALID_HANDLE)return false;double b[1];if(CopyBuffer(ema_handle,0,1,1,b)<=0)return false;v=b[0];return true;}
bool GetRSI(double &v){v=0.0;if(rsi_handle==INVALID_HANDLE)return false;double b[1];if(CopyBuffer(rsi_handle,0,1,1,b)<=0)return false;v=b[0];return true;}
double GetCandleBodyPercent(){double r=iHigh(_Symbol,PERIOD_CURRENT,1)-iLow(_Symbol,PERIOD_CURRENT,1);return(r<=0.0)?0.0:(MathAbs(iClose(_Symbol,PERIOD_CURRENT,1)-iOpen(_Symbol,PERIOD_CURRENT,1))/r)*100.0;}
double GetVolumeRatio(){double v1=(double)iVolume(_Symbol,PERIOD_CURRENT,1),v2=(double)iVolume(_Symbol,PERIOD_CURRENT,2),v3=(double)iVolume(_Symbol,PERIOD_CURRENT,3);double avg=(v1+v2+v3)/3.0;return(avg<=0.0)?0.0:v1/avg;}
double GetRangeRatio(){double r1=iHigh(_Symbol,PERIOD_CURRENT,1)-iLow(_Symbol,PERIOD_CURRENT,1);if(r1<=0.0)return 0.0;double sum=0.0;int cnt=0;for(int i=1;i<=PeriodoRange;i++){double r=iHigh(_Symbol,PERIOD_CURRENT,i)-iLow(_Symbol,PERIOD_CURRENT,i);if(r>0.0){sum+=r;cnt++;}}if(cnt==0)return 0.0;double avg=sum/cnt;return(avg<=0.0)?0.0:r1/avg;}
double GetDailyProfit(){ulong now=GetTickCount64();if(now-g_lastStatsUpdateTick<1000)return g_cachedDailyProfit;g_lastStatsUpdateTick=now;MqlDateTime dt;TimeToStruct(TimeCurrent(),dt);dt.hour=0;dt.min=0;dt.sec=0;if(!HistorySelect(StructToTime(dt),TimeCurrent()))return g_cachedDailyProfit;double p=0.0;int deals=HistoryDealsTotal();for(int i=0;i<deals;i++){ulong t=HistoryDealGetTicket(i);if(t==0)continue;p+=HistoryDealGetDouble(t,DEAL_PROFIT)+HistoryDealGetDouble(t,DEAL_SWAP)+HistoryDealGetDouble(t,DEAL_COMMISSION);}g_cachedDailyProfit=p;return p;}
double GetAccountDrawdownPercent(){if(g_initialEquity<=0.0)return 0.0;double dd=g_initialEquity-AccountInfoDouble(ACCOUNT_EQUITY);return(dd<=0.0)?0.0:(dd/g_initialEquity)*100.0;}
bool HasOpenPositions(){ulong now=GetTickCount64();if(now-g_lastHasPosTick<50)return g_cachedHasPos;g_lastHasPosTick=now;g_cachedHasPos=false;for(int i=0;i<PositionsTotal();i++){ulong t=PositionGetTicket(i);if(t==0)continue;if(PositionGetString(POSITION_SYMBOL)==_Symbol&&(ulong)PositionGetInteger(POSITION_MAGIC)==NumeroMagico){g_cachedHasPos=true;break;}}return g_cachedHasPos;}
void CloseAllPositions(){for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(t==0)continue;if(PositionGetString(POSITION_SYMBOL)==_Symbol&&(ulong)PositionGetInteger(POSITION_MAGIC)==NumeroMagico)trade.PositionClose(t);}}

//--- Variação M15: Filtro de Horário para evitar spreads altos
bool CheckHorario()
{
   if(!UsarFiltroHorario) return true;
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int horaAtual   = dt.hour;
   int minutoAtual = dt.min;
   int minutosAtual = horaAtual * 60 + minutoAtual;
   int minutosInicio = HoraInicioPermitido * 60 + MinutoInicioPermitido;
   int minutosFim    = HoraFimPermitido * 60 + MinutoFimPermitido;
   return (minutosAtual >= minutosInicio && minutosAtual < minutosFim);
}

bool CheckTrend(int &direction)
{
   direction=DIR_NONE;
   if(!AtivarMediaMovel){direction=DIR_BUY;return true;}
   double ema; if(!GetEMA(ema)) return false;
   double close1=iClose(_Symbol,PERIOD_CURRENT,1);
   if(close1>ema) direction=DIR_BUY;
   else if(close1<ema) direction=DIR_SELL;
   return(direction!=DIR_NONE);
}
bool CheckRSI(int direction)
{
   if(!UsarRSI) return true;
   double rsi; if(!GetRSI(rsi)) return false;
   if(RSI_ImpulsoMode) return(direction==DIR_BUY)?rsi>=50.0:rsi<=50.0;
   return(direction==DIR_BUY)?rsi<=RSI_Sobrevendido:rsi>=RSI_Sobrecomprado;
}
bool CheckCandleStrength(){return(!UsarForcaCandle)?true:GetCandleBodyPercent()>=CorpoCandleMinimo;}
bool CheckVolume(){return(!UsarVolume)?true:GetVolumeRatio()>=VolumeMinimo;}
bool CheckRangeAdaptive(){return(!UsarRangeAdaptativo)?true:GetRangeRatio()>=MultiplicadorRange;}
bool CanOpenNewPosition(){return g_AtivarEA&&!g_dailyBlocked&&!g_emergencyBlocked;}

void OpenPosition(int direction, double volume)
{
   if(!CanOpenNewPosition()) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK),bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(ask<=0.0||bid<=0.0) return;
   volume=NormalizeDouble(volume,2); if(volume<=0.0) return;
   double price=(direction==DIR_BUY?ask:bid);
   double tpDist=MoneyToPriceDistance(TP_USD,volume),slDist=MoneyToPriceDistance(SL_USD,volume);
   double tp=(tpDist>0.0)?((direction==DIR_BUY)?price+tpDist:price-tpDist):0.0;
   double sl=(slDist>0.0)?((direction==DIR_BUY)?price-slDist:price+slDist):0.0;
   trade.SetExpertMagicNumber(NumeroMagico);
   bool r=(direction==DIR_BUY)?trade.Buy(volume,_Symbol,price,sl,tp):trade.Sell(volume,_Symbol,price,sl,tp);
   if(!r&&ModoDebug)Print("ERRO: ",trade.ResultRetcodeDescription());
   else if(ModoDebug)Print("M15 ORDEM: ",(direction==DIR_BUY?"COMPRA":"VENDA")," Vol:",volume," P:",price," SL:",sl," TP:",tp);
}
void CheckDailyStops(){MqlDateTime dt;TimeToStruct(TimeCurrent(),dt);static int lY=0,lD=0;if(lY==0){lY=dt.year;lD=dt.day_of_year;}else if(dt.year!=lY||dt.day_of_year!=lD){g_dailyBlocked=false;lY=dt.year;lD=dt.day_of_year;}if(g_dailyBlocked)return;double dp=GetDailyProfit();if(g_MetaDiaria>0.0&&dp>=g_MetaDiaria){CloseAllPositions();g_dailyBlocked=true;}if(g_LimitePercaDiaria>0.0&&dp<=-g_LimitePercaDiaria){CloseAllPositions();g_dailyBlocked=true;}}
void CheckEmergencyStop(){if(g_emergencyBlocked||DrawdownEmergencia<=0.0)return;if(GetAccountDrawdownPercent()>=DrawdownEmergencia){CloseAllPositions();g_emergencyBlocked=true;}}

void UIPanel_Create()
{
   ObjectCreate(0,PP_BG,OBJ_RECTANGLE_LABEL,0,0,0);ObjectSetInteger(0,PP_BG,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,PP_BG,OBJPROP_XDISTANCE,10);ObjectSetInteger(0,PP_BG,OBJPROP_YDISTANCE,20);ObjectSetInteger(0,PP_BG,OBJPROP_XSIZE,240);ObjectSetInteger(0,PP_BG,OBJPROP_YSIZE,85);ObjectSetInteger(0,PP_BG,OBJPROP_BGCOLOR,C_BG_DARK);ObjectSetInteger(0,PP_BG,OBJPROP_BORDER_TYPE,BORDER_FLAT);ObjectSetInteger(0,PP_BG,OBJPROP_COLOR,C'30,50,80');ObjectSetInteger(0,PP_BG,OBJPROP_WIDTH,2);
   ObjectCreate(0,PP_TITLE,OBJ_LABEL,0,0,0);ObjectSetInteger(0,PP_TITLE,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,PP_TITLE,OBJPROP_XDISTANCE,22);ObjectSetInteger(0,PP_TITLE,OBJPROP_YDISTANCE,28);ObjectSetInteger(0,PP_TITLE,OBJPROP_FONTSIZE,10);ObjectSetInteger(0,PP_TITLE,OBJPROP_COLOR,C_TXT);ObjectSetString(0,PP_TITLE,OBJPROP_FONT,"Arial Bold");ObjectSetString(0,PP_TITLE,OBJPROP_TEXT,"PRICEPRO M15 – Classic");
   ObjectCreate(0,PP_PROFIT,OBJ_LABEL,0,0,0);ObjectSetInteger(0,PP_PROFIT,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,PP_PROFIT,OBJPROP_XDISTANCE,22);ObjectSetInteger(0,PP_PROFIT,OBJPROP_YDISTANCE,55);ObjectSetInteger(0,PP_PROFIT,OBJPROP_FONTSIZE,9);ObjectSetInteger(0,PP_PROFIT,OBJPROP_COLOR,C_TXT);ObjectSetString(0,PP_PROFIT,OBJPROP_FONT,"Arial");ObjectSetString(0,PP_PROFIT,OBJPROP_TEXT,"Lucro do Dia:");
   ObjectCreate(0,PP_VALUE,OBJ_LABEL,0,0,0);ObjectSetInteger(0,PP_VALUE,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,PP_VALUE,OBJPROP_XDISTANCE,130);ObjectSetInteger(0,PP_VALUE,OBJPROP_YDISTANCE,55);ObjectSetInteger(0,PP_VALUE,OBJPROP_FONTSIZE,11);ObjectSetInteger(0,PP_VALUE,OBJPROP_COLOR,C_OK);ObjectSetString(0,PP_VALUE,OBJPROP_FONT,"Arial Bold");ObjectSetString(0,PP_VALUE,OBJPROP_TEXT,"0.00 USD");
}
void UIPanel_Delete(){ObjectDelete(0,PP_BG);ObjectDelete(0,PP_TITLE);ObjectDelete(0,PP_PROFIT);ObjectDelete(0,PP_VALUE);}
void UIPanel_Update(){double dp=GetDailyProfit();string t=(dp>=0)?"+"+(DoubleToString(dp,2))+" USD":DoubleToString(dp,2)+" USD";ObjectSetString(0,PP_VALUE,OBJPROP_TEXT,t);ObjectSetInteger(0,PP_VALUE,OBJPROP_COLOR,(dp>=0)?C_OK:C_BAD);}

int FindBreakevenIndex(ulong t){int n=ArraySize(g_breakevenTickets);for(int i=0;i<n;i++)if(g_breakevenTickets[i]==t)return i;return -1;}
void AddBreakevenTicket(ulong t){if(FindBreakevenIndex(t)!=-1)return;int n=ArraySize(g_breakevenTickets);ArrayResize(g_breakevenTickets,n+1);ArrayResize(g_breakevenLastModifiedBar,n+1);g_breakevenTickets[n]=t;g_breakevenLastModifiedBar[n]=0;}
void RemoveBreakevenAt(int idx){int n=ArraySize(g_breakevenTickets);if(idx<0||idx>=n)return;for(int i=idx;i<n-1;i++){g_breakevenTickets[i]=g_breakevenTickets[i+1];g_breakevenLastModifiedBar[i]=g_breakevenLastModifiedBar[i+1];}ArrayResize(g_breakevenTickets,n-1);ArrayResize(g_breakevenLastModifiedBar,n-1);}
void PruneBreakevenTickets(){int n=ArraySize(g_breakevenTickets);for(int i=n-1;i>=0;i--){bool f=false;for(int j=0;j<PositionsTotal();j++){if(PositionGetTicket(j)==g_breakevenTickets[i]){f=true;break;}}if(!f)RemoveBreakevenAt(i);}}
void ManagePositionStops()
{
   PruneBreakevenTickets();
   datetime curBar=iTime(_Symbol,PERIOD_CURRENT,0);
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=PositionGetTicket(i);if(ticket==0)continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol||(ulong)PositionGetInteger(POSITION_MAGIC)!=NumeroMagico)continue;
      long type=PositionGetInteger(POSITION_TYPE);
      double openP=PositionGetDouble(POSITION_PRICE_OPEN),curSL=PositionGetDouble(POSITION_SL),curTP=PositionGetDouble(POSITION_TP);
      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID),ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      bool hsBE=(FindBreakevenIndex(ticket)!=-1);
      if(!hsBE){double diff=(type==POSITION_TYPE_BUY)?(bid-openP)/_Point:(openP-ask)/_Point;if(diff>=(double)BreakevenActivatePoints){double nSL=NormalizeDouble(openP,(int)_Digits);bool mv=(curSL<=0.0)||(type==POSITION_TYPE_BUY&&nSL>curSL+MinMovePoints*_Point)||(type==POSITION_TYPE_SELL&&nSL<curSL-MinMovePoints*_Point);if(mv){bool mod=trade.PositionModify(ticket,nSL,curTP);if(ModoDebug)Print("BE M15 t=",ticket," SL=",nSL," ok=",mod);AddBreakevenTicket(ticket);int idx=FindBreakevenIndex(ticket);if(idx!=-1)g_breakevenLastModifiedBar[idx]=curBar;}}}
      else if(AtivarTrailingPorCandle){int idx=FindBreakevenIndex(ticket);datetime prevBar=iTime(_Symbol,PERIOD_CURRENT,1);if(prevBar==0||(idx!=-1&&g_breakevenLastModifiedBar[idx]==prevBar))continue;double nSL=NormalizeDouble((type==POSITION_TYPE_BUY)?iLow(_Symbol,PERIOD_CURRENT,1):iHigh(_Symbol,PERIOD_CURRENT,1),(int)_Digits);bool mv=(curSL<=0.0)?((type==POSITION_TYPE_BUY&&nSL>=openP+MinMovePoints*_Point)||(type==POSITION_TYPE_SELL&&nSL<=openP-MinMovePoints*_Point)):((type==POSITION_TYPE_BUY&&nSL>curSL+MinMovePoints*_Point)||(type==POSITION_TYPE_SELL&&nSL<curSL-MinMovePoints*_Point));if(mv&&MathAbs(nSL-curSL)>=_Point*MinMovePoints){bool mod=trade.PositionModify(ticket,nSL,curTP);if(ModoDebug)Print("Trail M15 t=",ticket," SL=",nSL," ok=",mod);if(idx==-1)AddBreakevenTicket(ticket);idx=FindBreakevenIndex(ticket);if(idx!=-1)g_breakevenLastModifiedBar[idx]=prevBar;}}
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   if(!CheckLicense()){Alert("Licença inválida.");return INIT_FAILED;}
   if(Period()!=TempoGrafico) Print("Aviso: Este EA é otimizado para M15.");
   trade.SetExpertMagicNumber(NumeroMagico);
   g_initialEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_MetaDiaria=MetaDiaria;g_LimitePercaDiaria=LimitePercaDiaria;g_AtivarEA=AtivarEA;
   ema_handle=iMA(_Symbol,PERIOD_CURRENT,PeriodoMediaMovel,0,TipoMedia,PRICE_CLOSE);if(ema_handle==INVALID_HANDLE){Print("Erro EMA");return INIT_FAILED;}
   rsi_handle=iRSI(_Symbol,PERIOD_CURRENT,PeriodoRSI,PRICE_CLOSE);if(rsi_handle==INVALID_HANDLE){Print("Erro RSI");return INIT_FAILED;}
   UIPanel_Create();
   Print("PRICEPRO M15 - Classic Refined iniciado | Magic=",NumeroMagico," | EMA=",PeriodoMediaMovel," | RSI=",PeriodoRSI," | Horário=",HoraInicioPermitido,"h",MinutoInicioPermitido,"m-",HoraFimPermitido,"h",MinutoFimPermitido,"m");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){if(ema_handle!=INVALID_HANDLE)IndicatorRelease(ema_handle);if(rsi_handle!=INVALID_HANDLE)IndicatorRelease(rsi_handle);UIPanel_Delete();}

void OnTick()
{
   static ulong s_fc=0;ulong nowT=GetTickCount64();
   if(nowT-s_fc>200){CheckDailyStops();CheckEmergencyStop();s_fc=nowT;}
   if(nowT-g_lastPanelUpdate>1000){UIPanel_Update();g_lastPanelUpdate=nowT;}

   if(IsNewBar())
   {
      if(!CheckHorario())
      {
         if(ModoDebug) Print("M15: Fora do horário permitido");
         return;
      }
      int dir;
      if(!CheckTrend(dir)||dir==DIR_NONE) return;
      if(!CanOpenNewPosition()||HasOpenPositions()) return;

      double rsiVal=0.0;GetRSI(rsiVal);
      bool okRSI    =CheckRSI(dir);
      bool okCandle =CheckCandleStrength();
      bool okVol    =CheckVolume();
      bool okRange  =CheckRangeAdaptive();

      if(ModoDebug)
      {
         string d=(dir==DIR_BUY?"COMPRA":"VENDA");
         Print("M15 [",d,"] RSI=",DoubleToString(rsiVal,1)," ok=",okRSI,
               " Candle=",DoubleToString(GetCandleBodyPercent(),1),"% ok=",okCandle,
               " Vol=",DoubleToString(GetVolumeRatio(),2)," ok=",okVol,
               " Range=",DoubleToString(GetRangeRatio(),2)," ok=",okRange);
      }

      if(okRSI&&okCandle&&okVol&&okRange)
      {
         double vol=CalculateLotSize();if(vol<=0.0)vol=0.01;
         OpenPosition(dir,vol);
      }
   }
   ManagePositionStops();
}
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam){}
