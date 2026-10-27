"""Explicit editable ARKit-like video score to existing rig diagnostic observation mapping.
Reading CTRL_expressions is read-only. Only Faceboard plugs are ever keyed.
"""

def observations():
    rows={}
    def put(raw,score,gain=1.):rows[raw]={score:gain}
    put('jawOpen','jawOpen');put('jawLeft','jawLeft');put('jawRight','jawRight');put('jawFwd','jawForward',.6)
    put('mouthLeft','mouthLeft');put('mouthRight','mouthRight')
    for side,label in [('L','Left'),('R','Right')]:
        for raw,score in [('browDown','browDown'),('browRaiseOuter','browOuterUp'),('eyeBlink','eyeBlink'),
            ('eyeWiden','eyeWide'),('eyeSquintInner','eyeSquint'),('eyeCheekRaise','cheekSquint'),
            ('noseWrinkle','noseSneer'),('mouthCornerPull','mouthSmile'),('mouthCornerDepress','mouthFrown'),
            ('mouthDimple','mouthDimple'),('mouthStretch','mouthStretch'),('mouthUpperLipRaise','mouthUpperUp'),
            ('mouthLowerLipDepress','mouthLowerDown')]:put(raw+side,score+label)
        put('browRaiseIn'+side,'browInnerUp')
        put('mouthCheekBlow'+side,'cheekPuff',.65)
        for level in ('U','D'):
            put('mouthPress'+level+side,'mouthPress'+label,.6)
            put('mouthFunnel'+level+side,'mouthFunnel',.8)
            put('mouthLipsPurse'+level+side,'mouthPucker',.8)
            put('mouthLipsTogether'+level+side,'mouthClose',.7)
        put('mouthUpperLipRollIn'+side,'mouthRollUpper',.65)
        put('mouthLowerLipRollIn'+side,'mouthRollLower',.65)
        put('jawChinRaiseU'+side,'mouthShrugUpper',.6)
        put('jawChinRaiseD'+side,'mouthShrugLower',.6)
        # Anatomical sides; inputs must be unmirrored.
        put('eyeLookUp'+side,'eyeLookUp'+label,.6);put('eyeLookDown'+side,'eyeLookDown'+label,.6)
        put('eyeLookLeft'+side,'eyeLookOut'+label if side=='L' else 'eyeLookIn'+label,.6)
        put('eyeLookRight'+side,'eyeLookIn'+label if side=='L' else 'eyeLookOut'+label,.6)
    return rows
