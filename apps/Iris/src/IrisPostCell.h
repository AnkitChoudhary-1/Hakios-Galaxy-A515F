// IrisPostCell.h - Reusable feed post cell
#import <UIKit/UIKit.h>
#import "IrisData.h"

@protocol IrisPostCellDelegate <NSObject>
@optional
- (void)postCell:(id)cell didTapUser:(NSString *)username;
- (void)postCell:(id)cell didTapMediaForPost:(IrisPost *)post;
- (void)postCell:(id)cell didTapLikeForPost:(IrisPost *)post;
- (void)postCell:(id)cell didTapCommentForPost:(IrisPost *)post;
- (void)postCell:(id)cell didTapShareForPost:(IrisPost *)post;
- (void)postCell:(id)cell didTapBookmarkForPost:(IrisPost *)post;
- (void)postCell:(id)cell didTapMoreForPost:(IrisPost *)post;
@end

@interface IrisPostCell : UITableViewCell

@property (nonatomic, weak) id<IrisPostCellDelegate> delegate;
@property (nonatomic, strong, readonly) IrisPost *post;

- (void)configureWithPost:(IrisPost *)post;
- (void)updateTheme;

+ (CGFloat)heightForPost:(IrisPost *)post width:(CGFloat)width;

@end
