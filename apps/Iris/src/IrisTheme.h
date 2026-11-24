// IrisTheme.h - Design system and dynamic theme management for Iris
#import <UIKit/UIKit.h>

extern NSString * const IrisThemeDidChangeNotification;

@interface IrisTheme : NSObject

@property (nonatomic, assign) BOOL isDarkMode;

+ (instancetype)sharedTheme;
- (void)toggleTheme;

// Semantic colors
- (UIColor *)mainBackgroundColor;
- (UIColor *)secondaryBackgroundColor;
- (UIColor *)cardBackgroundColor;
- (UIColor *)primaryTextColor;
- (UIColor *)secondaryTextColor;
- (UIColor *)mutedTextColor;
- (UIColor *)accentVioletColor;
- (UIColor *)accentPinkColor;
- (UIColor *)successColor;
- (UIColor *)errorColor;
- (UIColor *)dividerColor;
- (UIColor *)glassSurfaceColor;
- (UIColor *)glassBorderColor;

// Helpers
+ (UIColor *)colorWithHex:(uint32_t)hex alpha:(CGFloat)alpha;
+ (CAGradientLayer *)brandGradientLayerForFrame:(CGRect)frame;
+ (UIImage *)gradientRingImageWithSize:(CGSize)size strokeWidth:(CGFloat)width;
+ (UIImage *)iconNamed:(NSString *)name size:(CGSize)size color:(UIColor *)color filled:(BOOL)filled;

@end
