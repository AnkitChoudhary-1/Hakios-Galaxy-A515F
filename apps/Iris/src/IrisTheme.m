// IrisTheme.m - Design system implementation for Iris
#import "IrisTheme.h"

NSString * const IrisThemeDidChangeNotification = @"IrisThemeDidChangeNotification";

@implementation IrisTheme

+ (instancetype)sharedTheme {
    static IrisTheme *sSharedTheme = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        sSharedTheme = [[IrisTheme alloc] init];
    });
    return sSharedTheme;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _isDarkMode = YES; // Dark mode is primary by design
    }
    return self;
}

- (void)toggleTheme {
    self.isDarkMode = !self.isDarkMode;
}

- (void)setIsDarkMode:(BOOL)isDarkMode {
    if (_isDarkMode != isDarkMode) {
        _isDarkMode = isDarkMode;
        [[NSNotificationCenter defaultCenter] postNotificationName:IrisThemeDidChangeNotification object:self];
    }
}

+ (UIColor *)colorWithHex:(uint32_t)hex alpha:(CGFloat)alpha {
    return [UIColor colorWithRed:((CGFloat)((hex >> 16) & 0xFF)) / 255.0
                           green:((CGFloat)((hex >> 8) & 0xFF)) / 255.0
                            blue:((CGFloat)(hex & 0xFF)) / 255.0
                           alpha:alpha];
}

- (UIColor *)mainBackgroundColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0x0B0B0D alpha:1.0] : [IrisTheme colorWithHex:0xFAFAFA alpha:1.0];
}

- (UIColor *)secondaryBackgroundColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0x151518 alpha:1.0] : [IrisTheme colorWithHex:0xFFFFFF alpha:1.0];
}

- (UIColor *)cardBackgroundColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0x1C1C20 alpha:1.0] : [IrisTheme colorWithHex:0xF4F4F5 alpha:1.0];
}

- (UIColor *)primaryTextColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0xFFFFFF alpha:1.0] : [IrisTheme colorWithHex:0x18181B alpha:1.0];
}

- (UIColor *)secondaryTextColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0xA1A1AA alpha:1.0] : [IrisTheme colorWithHex:0x71717A alpha:1.0];
}

- (UIColor *)mutedTextColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0x71717A alpha:1.0] : [IrisTheme colorWithHex:0xA1A1AA alpha:1.0];
}

- (UIColor *)accentVioletColor {
    return [IrisTheme colorWithHex:0x8B5CF6 alpha:1.0];
}

- (UIColor *)accentPinkColor {
    return [IrisTheme colorWithHex:0xEC4899 alpha:1.0];
}

- (UIColor *)successColor {
    return [IrisTheme colorWithHex:0x22C55E alpha:1.0];
}

- (UIColor *)errorColor {
    return [IrisTheme colorWithHex:0xEF4444 alpha:1.0];
}

- (UIColor *)dividerColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0x27272A alpha:0.6] : [IrisTheme colorWithHex:0xE4E4E7 alpha:0.8];
}

- (UIColor *)glassSurfaceColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0x151518 alpha:0.82] : [IrisTheme colorWithHex:0xFFFFFF alpha:0.88];
}

- (UIColor *)glassBorderColor {
    return self.isDarkMode ? [IrisTheme colorWithHex:0xFFFFFF alpha:0.12] : [IrisTheme colorWithHex:0x000000 alpha:0.08];
}

+ (CAGradientLayer *)brandGradientLayerForFrame:(CGRect)frame {
    CAGradientLayer *gradient = [CAGradientLayer layer];
    gradient.frame = frame;
    gradient.colors = @[
        (id)[IrisTheme colorWithHex:0x8B5CF6 alpha:1.0].CGColor,
        (id)[IrisTheme colorWithHex:0xEC4899 alpha:1.0].CGColor
    ];
    gradient.startPoint = CGPointMake(0.0, 0.0);
    gradient.endPoint = CGPointMake(1.0, 1.0);
    return gradient;
}

+ (UIImage *)gradientRingImageWithSize:(CGSize)size strokeWidth:(CGFloat)width {
    UIGraphicsBeginImageContextWithOptions(size, NO, 0.0);
    CGContextRef ctx = UIGraphicsGetCurrentContext();
    if (!ctx) return nil;
    
    CGRect rect = CGRectMake(width / 2.0, width / 2.0, size.width - width, size.height - width);
    CGContextSetLineWidth(ctx, width);
    
    // Draw gradient stroke using circular path
    UIBezierPath *path = [UIBezierPath bezierPathWithOvalInRect:rect];
    CGContextSaveGState(ctx);
    [path addClip];
    
    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    CGFloat colors[] = {
        0.545, 0.361, 0.965, 1.0, // 0x8B5CF6
        0.925, 0.282, 0.600, 1.0  // 0xEC4899
    };
    CGGradientRef grad = CGGradientCreateWithColorComponents(colorSpace, colors, NULL, 2);
    CGContextDrawLinearGradient(ctx, grad, CGPointMake(0, 0), CGPointMake(size.width, size.height), 0);
    CGGradientRelease(grad);
    CGColorSpaceRelease(colorSpace);
    CGContextRestoreGState(ctx);
    
    UIImage *img = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();
    return img;
}

+ (UIImage *)iconNamed:(NSString *)name size:(CGSize)size color:(UIColor *)color filled:(BOOL)filled {
    // Try system SF symbol first
    NSString *symbolName = nil;
    if ([name isEqualToString:@"home"]) symbolName = filled ? @"house.fill" : @"house";
    else if ([name isEqualToString:@"explore"]) symbolName = @"magnifyingglass";
    else if ([name isEqualToString:@"create"]) symbolName = filled ? @"plus.app.fill" : @"plus.app";
    else if ([name isEqualToString:@"activity"]) symbolName = filled ? @"heart.fill" : @"heart";
    else if ([name isEqualToString:@"profile"]) symbolName = filled ? @"person.crop.circle.fill" : @"person.crop.circle";
    else if ([name isEqualToString:@"like"]) symbolName = filled ? @"heart.fill" : @"heart";
    else if ([name isEqualToString:@"comment"]) symbolName = filled ? @"bubble.right.fill" : @"bubble.right";
    else if ([name isEqualToString:@"share"]) symbolName = @"paperplane";
    else if ([name isEqualToString:@"bookmark"]) symbolName = filled ? @"bookmark.fill" : @"bookmark";
    else if ([name isEqualToString:@"more"]) symbolName = @"ellipsis";
    else if ([name isEqualToString:@"close"]) symbolName = @"xmark";
    else if ([name isEqualToString:@"back"]) symbolName = @"chevron.backward";
    else if ([name isEqualToString:@"search"]) symbolName = @"magnifyingglass";
    else if ([name isEqualToString:@"grid"]) symbolName = @"squareshape.split.3x3";
    else if ([name isEqualToString:@"tag"]) symbolName = @"person.crop.square";
    else if ([name isEqualToString:@"play"]) symbolName = @"play.fill";
    else if ([name isEqualToString:@"sun"]) symbolName = @"sun.max.fill";
    else if ([name isEqualToString:@"moon"]) symbolName = @"moon.stars.fill";
    else if ([name isEqualToString:@"settings"]) symbolName = @"gearshape";
    else if ([name isEqualToString:@"notifications"]) symbolName = @"bell";
    else if ([name isEqualToString:@"messages"]) symbolName = @"bubble.left.and.bubble.right";
    
    if (symbolName) {
        UIImageSymbolConfiguration *config = [UIImageSymbolConfiguration configurationWithPointSize:size.height * 0.75 weight:UIImageSymbolWeightMedium];
        UIImage *sysImg = [UIImage systemImageNamed:symbolName withConfiguration:config];
        if (sysImg) {
            return [sysImg imageWithTintColor:color renderingMode:UIImageRenderingModeAlwaysOriginal];
        }
    }
    
    // Crisp custom vector drawing fallback if system symbols aren't present
    UIGraphicsBeginImageContextWithOptions(size, NO, 0.0);
    CGContextRef ctx = UIGraphicsGetCurrentContext();
    if (!ctx) return nil;
    [color set];
    
    CGFloat w = size.width;
    CGFloat h = size.height;
    
    if ([name isEqualToString:@"home"]) {
        UIBezierPath *p = [UIBezierPath bezierPath];
        [p moveToPoint:CGPointMake(w * 0.5, h * 0.15)];
        [p addLineToPoint:CGPointMake(w * 0.88, h * 0.46)];
        [p addLineToPoint:CGPointMake(w * 0.88, h * 0.88)];
        [p addLineToPoint:CGPointMake(w * 0.12, h * 0.88)];
        [p addLineToPoint:CGPointMake(w * 0.12, h * 0.46)];
        [p closePath];
        if (filled) [p fill]; else { p.lineWidth = 2.0; [p stroke]; }
    } else if ([name isEqualToString:@"explore"] || [name isEqualToString:@"search"]) {
        UIBezierPath *circle = [UIBezierPath bezierPathWithOvalInRect:CGRectMake(w * 0.15, h * 0.15, w * 0.55, h * 0.55)];
        circle.lineWidth = 2.0;
        [circle stroke];
        UIBezierPath *handle = [UIBezierPath bezierPath];
        [handle moveToPoint:CGPointMake(w * 0.58, h * 0.58)];
        [handle addLineToPoint:CGPointMake(w * 0.85, h * 0.85)];
        handle.lineWidth = 2.5;
        handle.lineCapStyle = kCGLineCapRound;
        [handle stroke];
    } else if ([name isEqualToString:@"create"]) {
        UIBezierPath *box = [UIBezierPath bezierPathWithRoundedRect:CGRectMake(w * 0.15, h * 0.15, w * 0.7, h * 0.7) cornerRadius:6.0];
        box.lineWidth = 2.0;
        [box stroke];
        UIBezierPath *plus = [UIBezierPath bezierPath];
        [plus moveToPoint:CGPointMake(w * 0.5, h * 0.3)];
        [plus addLineToPoint:CGPointMake(w * 0.5, h * 0.7)];
        [plus moveToPoint:CGPointMake(w * 0.3, h * 0.5)];
        [plus addLineToPoint:CGPointMake(w * 0.7, h * 0.5)];
        plus.lineWidth = 2.0;
        plus.lineCapStyle = kCGLineCapRound;
        [plus stroke];
    } else if ([name isEqualToString:@"activity"] || [name isEqualToString:@"like"]) {
        UIBezierPath *heart = [UIBezierPath bezierPath];
        [heart moveToPoint:CGPointMake(w * 0.5, h * 0.82)];
        [heart addCurveToPoint:CGPointMake(w * 0.1, h * 0.4) controlPoint1:CGPointMake(w * 0.3, h * 0.65) controlPoint2:CGPointMake(w * 0.1, h * 0.55)];
        [heart addArcWithCenter:CGPointMake(w * 0.3, h * 0.32) radius:w * 0.2 startAngle:M_PI endAngle:0 clockwise:YES];
        [heart addArcWithCenter:CGPointMake(w * 0.7, h * 0.32) radius:w * 0.2 startAngle:M_PI endAngle:0 clockwise:YES];
        [heart addCurveToPoint:CGPointMake(w * 0.5, h * 0.82) controlPoint1:CGPointMake(w * 0.9, h * 0.55) controlPoint2:CGPointMake(w * 0.7, h * 0.65)];
        [heart closePath];
        if (filled) [heart fill]; else { heart.lineWidth = 2.0; [heart stroke]; }
    } else if ([name isEqualToString:@"bookmark"]) {
        UIBezierPath *b = [UIBezierPath bezierPath];
        [b moveToPoint:CGPointMake(w * 0.22, h * 0.15)];
        [b addLineToPoint:CGPointMake(w * 0.78, h * 0.15)];
        [b addLineToPoint:CGPointMake(w * 0.78, h * 0.85)];
        [b addLineToPoint:CGPointMake(w * 0.5, h * 0.65)];
        [b addLineToPoint:CGPointMake(w * 0.22, h * 0.85)];
        [b closePath];
        if (filled) [b fill]; else { b.lineWidth = 2.0; [b stroke]; }
    } else if ([name isEqualToString:@"comment"]) {
        UIBezierPath *c = [UIBezierPath bezierPath];
        [c moveToPoint:CGPointMake(w * 0.5, h * 0.18)];
        [c addCurveToPoint:CGPointMake(w * 0.85, h * 0.48) controlPoint1:CGPointMake(w * 0.75, h * 0.18) controlPoint2:CGPointMake(w * 0.85, h * 0.3)];
        [c addCurveToPoint:CGPointMake(w * 0.5, h * 0.78) controlPoint1:CGPointMake(w * 0.85, h * 0.65) controlPoint2:CGPointMake(w * 0.72, h * 0.78)];
        [c addLineToPoint:CGPointMake(w * 0.3, h * 0.78)];
        [c addLineToPoint:CGPointMake(w * 0.15, h * 0.88)];
        [c addLineToPoint:CGPointMake(w * 0.22, h * 0.72)];
        [c addCurveToPoint:CGPointMake(w * 0.15, h * 0.48) controlPoint1:CGPointMake(w * 0.18, h * 0.65) controlPoint2:CGPointMake(w * 0.15, h * 0.58)];
        [c addCurveToPoint:CGPointMake(w * 0.5, h * 0.18) controlPoint1:CGPointMake(w * 0.15, h * 0.3) controlPoint2:CGPointMake(w * 0.3, h * 0.18)];
        [c closePath];
        if (filled) [c fill]; else { c.lineWidth = 2.0; [c stroke]; }
    } else if ([name isEqualToString:@"share"]) {
        UIBezierPath *plane = [UIBezierPath bezierPath];
        [plane moveToPoint:CGPointMake(w * 0.15, h * 0.5)];
        [plane addLineToPoint:CGPointMake(w * 0.85, h * 0.15)];
        [plane addLineToPoint:CGPointMake(w * 0.55, h * 0.85)];
        [plane addLineToPoint:CGPointMake(w * 0.42, h * 0.58)];
        [plane closePath];
        plane.lineWidth = 2.0;
        plane.lineJoinStyle = kCGLineJoinRound;
        [plane stroke];
    } else if ([name isEqualToString:@"more"]) {
        for (int i = 0; i < 3; i++) {
            CGRect dotRect = CGRectMake(w * (0.2 + i * 0.27) - 2.5, h * 0.5 - 2.5, 5, 5);
            UIBezierPath *dot = [UIBezierPath bezierPathWithOvalInRect:dotRect];
            [dot fill];
        }
    } else if ([name isEqualToString:@"close"]) {
        UIBezierPath *x = [UIBezierPath bezierPath];
        [x moveToPoint:CGPointMake(w * 0.25, h * 0.25)];
        [x addLineToPoint:CGPointMake(w * 0.75, h * 0.75)];
        [x moveToPoint:CGPointMake(w * 0.75, h * 0.25)];
        [x addLineToPoint:CGPointMake(w * 0.25, h * 0.75)];
        x.lineWidth = 2.5;
        x.lineCapStyle = kCGLineCapRound;
        [x stroke];
    } else if ([name isEqualToString:@"back"]) {
        UIBezierPath *arr = [UIBezierPath bezierPath];
        [arr moveToPoint:CGPointMake(w * 0.65, h * 0.25)];
        [arr addLineToPoint:CGPointMake(w * 0.35, h * 0.5)];
        [arr addLineToPoint:CGPointMake(w * 0.65, h * 0.75)];
        arr.lineWidth = 2.5;
        arr.lineCapStyle = kCGLineCapRound;
        [arr stroke];
    } else if ([name isEqualToString:@"play"]) {
        UIBezierPath *tri = [UIBezierPath bezierPath];
        [tri moveToPoint:CGPointMake(w * 0.35, h * 0.25)];
        [tri addLineToPoint:CGPointMake(w * 0.75, h * 0.5)];
        [tri addLineToPoint:CGPointMake(w * 0.35, h * 0.75)];
        [tri closePath];
        [tri fill];
    } else {
        // Generic circle indicator
        UIBezierPath *circ = [UIBezierPath bezierPathWithOvalInRect:CGRectMake(w * 0.2, h * 0.2, w * 0.6, h * 0.6)];
        circ.lineWidth = 2.0;
        [circ stroke];
    }
    
    UIImage *res = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();
    return res;
}

@end
