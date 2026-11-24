// IrisTopNavBar.h - Top navigation bar for Iris Home Feed
#import <UIKit/UIKit.h>

@protocol IrisTopNavBarDelegate <NSObject>
@optional
- (void)topNavBarDidTapThemeToggle;
- (void)topNavBarDidTapNotifications;
- (void)topNavBarDidTapMessages;
@end

@interface IrisTopNavBar : UIView

@property (nonatomic, weak) id<IrisTopNavBarDelegate> delegate;

- (void)updateTheme;

@end
